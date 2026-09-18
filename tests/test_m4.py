from fastapi.testclient import TestClient
from app.main import app
from app.services.capabilities import capability_registry

client = TestClient(app)

def test_capability_registry_has_execute():
    assert capability_registry.get("execute") is not None

def test_mission_completes_and_task_is_persisted():
    r = client.post("/v1/missions", json={"objective": "Create a design for UNIPARC"})
    assert r.status_code == 200
    task_id = r.json()["task"]["id"]
    task = client.get(f"/v1/tasks/{task_id}")
    assert task.status_code == 200
    assert task.json()["status"] in {"queued", "running", "completed"}
