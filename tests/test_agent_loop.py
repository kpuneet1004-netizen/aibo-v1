from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_mission_has_plan_and_verified_result():
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
