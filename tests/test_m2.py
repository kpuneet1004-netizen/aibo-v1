from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_create_mission():
    r=client.post("/v1/missions",json={"objective":"Create a design for UNIPARC"})
    assert r.status_code==200
    assert r.json()["mission"]["objective"]=="Create a design for UNIPARC"
    assert r.json()["task"]["agent"]=="design"

def test_missing_mission():
    assert client.get("/v1/missions/does-not-exist").status_code==404

def test_worker_endpoint():
    r=client.get("/v1/worker"); assert r.status_code==200; assert "queue_size" in r.json()
