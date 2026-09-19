from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.services.llm import llm_client
from app.services.planner import Planner, PlannerError

client = TestClient(app)

def test_mission_has_plan():
    response = client.post("/v1/missions", json={"objective": "Explain the current objective"})
    assert response.status_code == 200
    mission_id = response.json()["mission"]["id"]
    mission = client.get(f"/v1/missions/{mission_id}")
    assert mission.status_code == 200
    body = mission.json()
    assert body["plan"]
    assert body["plan"][0]["capability"] == "respond"

def test_planner_does_not_route_by_keyword():
    first = client.post("/v1/missions", json={"objective": "design a report"})
    second = client.post("/v1/missions", json={"objective": "design a report"})
    assert first.json()["task"]["agent"] == second.json()["task"]["agent"] == "general"
    assert first.json()["task"]["action"] == second.json()["task"]["action"] == "respond"

def test_planner_rejects_unknown_capability(monkeypatch):
    def fake_plan(objective, runtime_contract=None):
        return {
            "steps": [{
                "id": "step-1",
                "objective": objective,
                "capability": "browser",
                "agent": "general",
                "payload": {},
                "requires_approval": False,
            }]
        }

    monkeypatch.setattr(llm_client, "plan", fake_plan)
    with pytest.raises(PlannerError, match="unsupported capability"):
        Planner().plan("Browse the web")

def test_planner_rejects_unknown_agent_pair(monkeypatch):
    def fake_plan(objective, runtime_contract=None):
        return {
            "steps": [{
                "id": "step-1",
                "objective": objective,
                "capability": "respond",
                "agent": "design",
                "payload": {},
                "requires_approval": False,
            }]
        }

    monkeypatch.setattr(llm_client, "plan", fake_plan)
    with pytest.raises(PlannerError, match="unsupported agent/capability pair"):
        Planner().plan("Respond to me")
