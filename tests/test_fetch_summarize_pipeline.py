import time
from uuid import uuid4
import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.models.task import MissionTask, TaskStatus
from app.services.capabilities import capability_registry, _verify_summarize_text
from app.services.executor import task_executor
from app.services.llm import llm_client
from app.services.missions import mission_store
from app.services.tasks import task_store
from app.services.verification import VerificationError, verifier


def test_stub_planner_creates_fetch_then_summarize():
    plan = llm_client.plan("Please read https://example.com/article and summarize it")
    assert [step["capability"] for step in plan["steps"]] == ["fetch_url", "summarize_text"]
    assert plan["steps"][1]["depends_on"] == ["step-1"]
    assert plan["steps"][1]["payload"] == {}


def test_summarize_verification_rejects_summary_longer_than_source():
    with __import__("pytest").raises(VerificationError):
        verifier.verify("summarize_text", {"summary": "x" * 11, "source_chars": 10})


def test_stub_summarizer_bounds_punctuation_free_text():
    text = "x" * 5000
    summary = llm_client.summarize(text)
    assert len(summary) == 280
    assert len(summary) <= len(text)


def test_dependency_output_is_scoped_to_mission():
    owner = f"owner-{uuid4()}"
    mission_a = mission_store.create("mission a", owner_id=owner)
    mission_b = mission_store.create("mission b", owner_id=owner)
    foreign = MissionTask(id=str(uuid4()), mission_id=mission_b.id, agent="general", action="fetch_url", payload={"url": "https://example.com"}, status=TaskStatus.COMPLETED, result={"output": {"text": "secret"}, "verification": {"verified": True}})
    task = MissionTask(id=str(uuid4()), mission_id=mission_a.id, agent="general", action="summarize_text", payload={}, depends_on=[foreign.id], max_retries=0)
    task_store.save(foreign)
    task_store.save(task)
    result = task_executor.execute(task)
    assert result.status == TaskStatus.FAILED
    assert "Dependency task not found in mission" in (result.error or "")


def test_failed_dependency_cascades_to_queued_dependents():
    mission = mission_store.create("cascade", owner_id=f"owner-{uuid4()}")
    failed = MissionTask(id=str(uuid4()), mission_id=mission.id, agent="general", action="respond", payload={}, max_retries=0)
    dependent = MissionTask(id=str(uuid4()), mission_id=mission.id, agent="general", action="summarize_text", payload={}, depends_on=[failed.id], max_retries=0)
    task_store.save(failed)
    task_store.save(dependent)
    result = task_executor.execute(failed)
    assert result.status == TaskStatus.FAILED
    refreshed = task_store.get(dependent.id)
    assert refreshed is not None
    assert refreshed.status == TaskStatus.FAILED
    assert "Blocked by failed dependency" in (refreshed.error or "")


def test_unknown_capability_cannot_verify():
    with __import__("pytest").raises(VerificationError):
        verifier.verify("does_not_exist", {"text": "x"})


def test_fetch_summarize_mission_completes_end_to_end_via_api(monkeypatch):
    from app.services import capabilities

    original_get = httpx.Client.get
    fake_text = "Aibo is a personal assistant. This article demonstrates a deterministic test fetch."

    def fake_resolve(url):
        return "https", "example.com", "93.184.216.34", 443

    def selective_get(client, url, *args, **kwargs):
        if "93.184.216.34" in str(url):
            return httpx.Response(200, request=httpx.Request("GET", str(url)), headers={"content-type": "text/plain"}, content=fake_text.encode())
        return original_get(client, url, *args, **kwargs)

    monkeypatch.setattr(capabilities, "_resolve_pinned_address", fake_resolve)
    monkeypatch.setattr(httpx.Client, "get", selective_get)

    with TestClient(app) as client:
        response = client.post("/v1/missions", json={"objective": "Please read https://example.com/article and summarize it"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert [task["action"] for task in body["tasks"]] == ["fetch_url", "summarize_text"]
        assert body["tasks"][1]["depends_on"] == [body["tasks"][0]["id"]]
        assert body["tasks"][1]["depends_on"] != ["step-1"]

        deadline = time.time() + 5
        while time.time() < deadline:
            mission = client.get(f"/v1/missions/{body['mission']['id']}")
            if mission.status_code == 200 and mission.json()["status"] == "completed":
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"mission did not complete: {mission.text}")

        summarize_task = client.get(f"/v1/tasks/{body['tasks'][1]['id']}").json()
        assert summarize_task["status"] == "completed"
        assert summarize_task["result"]["verification"]["verified"] is True
        assert fake_text.split(".")[0] in summarize_task["result"]["output"]["summary"]
