from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_mission_uses_planner():
    response = client.post("/v1/missions", json={"objective": "Create a design for UNIPARC"})
    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["objective"] == "Create a design for UNIPARC"
    assert body["mission"]["status"] in {"running", "completed"}
    assert body["task"]["agent"] == "general"
    assert body["task"]["action"] == "respond"

def test_missing_mission():
    assert client.get("/v1/missions/does-not-exist").status_code == 404

def test_worker_endpoint():
    response = client.get("/v1/worker")
    assert response.status_code == 200
    assert "queue_size" in response.json()
