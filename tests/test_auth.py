from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)


def test_session_exchange_and_bearer_auth(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    monkeypatch.setattr(settings, "session_ttl_seconds", 300)

    session = client.post("/v1/session", headers={"X-Aibo-API-Key": "test-secret"})
    assert session.status_code == 200
    body = session.json()
    assert body["token_type"] == "Bearer"
    assert body["token"]

    status = client.get(
        "/v1/status",
        headers={"Authorization": f"Bearer {body['token']}"},
    )
    assert status.status_code == 200


def test_invalid_bearer_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    response = client.get(
        "/v1/status",
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401
