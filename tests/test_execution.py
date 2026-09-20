from uuid import uuid4

import httpx
import pytest
import socket

from app.models.mission import MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.capabilities import CapabilityDefinition, capability_registry, fetch_url
from app.services.executor import task_executor
from app.services.missions import mission_store
from app.services.queue import task_queue
from app.services.tasks import task_store

def test_executor_verifies_and_completes_mission():
    mission = mission_store.create("Verify an Aibo response")
    task = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="respond",
        payload={"objective": "Verify an Aibo response"},
    )
    task_store.save(task)

    result = task_executor.execute(task)

    assert result.status == TaskStatus.COMPLETED
    assert result.result["verification"]["verified"] is True
    assert mission_store.get(mission.id).status == MissionStatus.COMPLETED

def test_fetch_url_returns_verified_http_result(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    class FakeResponse:
        url = "https://example.com"
        status_code = 200
        headers = {"content-type": "text/plain"}
        content = b"hello aibo"
        text = "hello aibo"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: FakeResponse())
    result = fetch_url({"url": "https://example.com"})
    assert result["status_code"] == 200
    assert result["text"] == "hello aibo"

def test_fetch_url_rejects_private_hosts():
    with pytest.raises(ValueError, match="private or local"):
        fetch_url({"url": "http://127.0.0.1:8000"})

def test_executor_runs_real_fetch_capability(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    class FakeResponse:
        url = "https://example.com"
        status_code = 200
        headers = {"content-type": "text/plain"}
        content = b"mission complete"
        text = "mission complete"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: FakeResponse())
    mission = mission_store.create("Fetch https://example.com")
    task = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="fetch_url",
        payload={"url": "https://example.com"},
    )
    task_store.save(task)
    result = task_executor.execute(task)
    assert result.status == TaskStatus.COMPLETED
    assert result.result["output"]["status_code"] == 200
    assert result.result["verification"]["verified"] is True


def test_fetch_url_rejects_hostname_resolving_to_private_ip(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))],
    )
    with pytest.raises(ValueError, match="hostname resolves to a private or local IP"):
        fetch_url({"url": "http://example.com"})


def test_worker_recovers_orphaned_running_task():
    from app.services.worker import Worker
    import time
    mission = mission_store.create("Recover orphaned task")
    task = MissionTask(id=str(uuid4()), mission_id=mission.id, agent="general",
        action="respond", payload={"objective": "Recover orphaned task"}, status=TaskStatus.RUNNING)
    task_store.save(task)
    worker = Worker()
    worker.start()
    deadline = time.time() + 3
    while time.time() < deadline:
        if task_store.get(task.id).status == TaskStatus.COMPLETED:
            break
        time.sleep(0.05)
    worker.stop()
    assert task_store.get(task.id).status == TaskStatus.COMPLETED


def test_worker_survives_unhandled_executor_exception(monkeypatch):
    from app.services.worker import Worker
    import time
    mission = mission_store.create("Worker survives exception")
    task = MissionTask(id=str(uuid4()), mission_id=mission.id, agent="general",
        action="respond", payload={"objective": "Worker survives exception"})
    task_store.save(task)
    worker = Worker()
    original_evaluate = __import__("app.services.permissions", fromlist=["permission_policy"]).permission_policy.evaluate
    calls = {"count": 0}

    def explode_once(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        return original_evaluate(*args, **kwargs)

    monkeypatch.setattr(
        __import__("app.services.permissions", fromlist=["permission_policy"]).permission_policy,
        "evaluate",
        explode_once,
    )
    worker.start()
    worker.enqueue(task)
    deadline = time.time() + 3
    while time.time() < deadline:
        current = task_store.get(task.id)
        if current and current.status == TaskStatus.COMPLETED:
            break
        time.sleep(0.05)
    assert worker.running is True
    assert task_store.get(task.id).attempts == 2
    worker.stop()
    assert worker.running is False


def test_executor_pauses_for_approval_instead_of_retrying(monkeypatch):
    called = {"count": 0}

    def should_not_execute(payload):
        called["count"] += 1
        return {"ok": True}

    capability_registry.register(CapabilityDefinition(
        "test_external_write",
        "Test approval-gated external write.",
        "external_write",
        False,
        should_not_execute,
    ))
    mission = mission_store.create("Approval-gated action")
    task = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="test_external_write",
        payload={},
        max_retries=3,
    )
    task_store.save(task)

    result = task_executor.execute(task)

    assert result.status == TaskStatus.WAITING_APPROVAL
    assert result.attempts == 1
    assert result.approval_granted is False
    assert called["count"] == 0
    assert mission_store.get(mission.id).status == MissionStatus.WAITING_APPROVAL


def test_worker_does_not_retry_approval_wait(monkeypatch):
    from app.services.worker import Worker
    import time

    called = {"count": 0}

    def should_not_execute(payload):
        called["count"] += 1
        return {"ok": True}

    capability_registry.register(CapabilityDefinition(
        "test_external_write_worker",
        "Test worker approval pause.",
        "external_write",
        False,
        should_not_execute,
    ))
    mission = mission_store.create("Worker approval pause")
    task = MissionTask(
        id=str(uuid4()),
        mission_id=mission.id,
        agent="general",
        action="test_external_write_worker",
        payload={},
        max_retries=3,
    )
    task_store.save(task)

    worker = Worker()
    worker.start()
    deadline = time.time() + 3
    while time.time() < deadline:
        current = task_store.get(task.id)
        if current and current.status == TaskStatus.WAITING_APPROVAL:
            break
        time.sleep(0.05)

    time.sleep(0.2)
    current = task_store.get(task.id)
    assert current.status == TaskStatus.WAITING_APPROVAL
    assert current.attempts == 1
    assert called["count"] == 0
    assert task_queue.size() == 0
    worker.stop()
