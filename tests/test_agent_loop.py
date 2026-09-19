from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models.task import MissionTask, TaskStatus
from app.services.capabilities import capability_registry
from app.services.llm import llm_client
from app.services.planner import Planner, PlannerError
from app.services.tasks import task_store

client = TestClient(app)

def test_mission_has_plan():
    response = client.post("/v1/missions", json={"objective": "Explain the current objective"})
    assert response.status_code == 200
    mission_id = response.json()["mission"]["id"]
    mission = client.get(f"/v1/missions/{mission_id}")
    assert mission.status_code == 200
    assert mission.json()["plan"]
    assert mission.json()["plan"][0]["capability"] == "respond"

def test_planner_does_not_route_by_keyword():
    first = client.post("/v1/missions", json={"objective": "design a report"})
    second = client.post("/v1/missions", json={"objective": "design a report"})
    assert first.json()["task"]["agent"] == second.json()["task"]["agent"] == "general"
    assert first.json()["task"]["action"] == second.json()["task"]["action"] == "respond"

def test_planner_rejects_unknown_capability(monkeypatch):
    def fake_plan(objective, runtime_contract=None):
        return {"steps": [{"id":"step-1","objective":objective,"capability":"browser","agent":"general","payload":{},"requires_approval":False}]}
    monkeypatch.setattr(llm_client, "plan", fake_plan)
    with pytest.raises(PlannerError, match="unsupported capability"):
        Planner().plan("Browse the web")

def test_planner_rejects_unknown_agent_pair(monkeypatch):
    def fake_plan(objective, runtime_contract=None):
        return {"steps": [{"id":"step-1","objective":objective,"capability":"respond","agent":"design","payload":{},"requires_approval":False}]}
    monkeypatch.setattr(llm_client, "plan", fake_plan)
    with pytest.raises(PlannerError, match="unsupported agent/capability pair"):
        Planner().plan("Respond to me")

def test_planner_rejects_dependency_cycle(monkeypatch):
    def fake_plan(objective, runtime_contract=None):
        return {"steps": [
            {"id":"a","objective":"a","capability":"respond","agent":"general","payload":{},"requires_approval":False,"depends_on":["b"]},
            {"id":"b","objective":"b","capability":"respond","agent":"general","payload":{},"requires_approval":False,"depends_on":["a"]},
        ]}
    monkeypatch.setattr(llm_client, "plan", fake_plan)
    with pytest.raises(PlannerError, match="cyclic"):
        Planner().plan("Do two dependent things")

def test_task_readiness_follows_dependencies():
    mission_id = str(uuid4())
    first = MissionTask(id=str(uuid4()), mission_id=mission_id, agent="general", action="respond", payload={})
    second = MissionTask(id=str(uuid4()), mission_id=mission_id, agent="general", action="respond", payload={"_depends_on":[first.id]})
    task_store.save(first); task_store.save(second)
    assert [task.id for task in task_store.ready_for_mission(mission_id)] == [first.id]
    first.status = TaskStatus.COMPLETED; task_store.save(first)
    assert [task.id for task in task_store.ready_for_mission(mission_id)] == [second.id]

def test_stub_planner_selects_fetch_url_for_url_objective():
    plan = llm_client.plan("Fetch https://example.com and inspect it")
    assert plan["steps"][0]["capability"] == "fetch_url"
    assert plan["steps"][0]["agent"] == "general"

def test_capability_contract_contains_risk_and_approval_metadata():
    contract = capability_registry.contract()
    fetch = next(item for item in contract if item["name"] == "fetch_url")
    assert fetch["risk"] == "external_read"
    assert fetch["requires_approval"] is False
