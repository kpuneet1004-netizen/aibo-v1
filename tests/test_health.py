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


def test_v1_requires_api_key_in_production(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "api_key", "test-secret")

    response = client.get("/v1/worker")
    assert response.status_code == 401

    response = client.get("/v1/worker", headers={"X-Aibo-API-Key": "test-secret"})
    assert response.status_code == 200
