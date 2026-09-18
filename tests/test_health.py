from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status() -> None:
    response = client.get("/v1/status")
    assert response.status_code == 200
    assert response.json()["agents"] >= 3
