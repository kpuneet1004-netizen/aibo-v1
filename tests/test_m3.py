from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_task_is_retrievable():
    r=client.post("/v1/missions",json={"objective":"Create a design for persistence"})
    assert r.status_code==200
    task_id=r.json()["task"]["id"]
    task=client.get(f"/v1/tasks/{task_id}")
    assert task.status_code==200
    assert task.json()["id"]==task_id

def test_status_exposes_worker():
    r=client.get("/v1/status")
    assert r.status_code==200
    assert "worker_running" in r.json()
