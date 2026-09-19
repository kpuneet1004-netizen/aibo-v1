from uuid import uuid4

import httpx
import pytest

from app.models.mission import MissionStatus
from app.models.task import MissionTask, TaskStatus
from app.services.capabilities import fetch_url
from app.services.executor import task_executor
from app.services.missions import mission_store
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
