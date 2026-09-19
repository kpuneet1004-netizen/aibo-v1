import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_session_cookie():
    client.cookies.clear()
    yield
    client.cookies.clear()


def test_session_exchange_sets_httponly_cookie_and_bearer_auth(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    monkeypatch.setattr(settings, "session_ttl_seconds", 300)

    session = client.post("/v1/session", headers={"X-Aibo-API-Key": "test-secret"})
    assert session.status_code == 200
    body = session.json()
    assert body["token_type"] == "Bearer"
    assert body["token"]

    cookie = session.cookies.get("aibo_session")
    assert cookie == body["token"]
    set_cookie = session.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie

    status = client.get("/v1/status", headers={"Authorization": f"Bearer {body['token']}"})
    assert status.status_code == 200


def test_session_cookie_auth_works_without_bearer_header(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    monkeypatch.setattr(settings, "session_ttl_seconds", 300)

    session = client.post("/v1/session", headers={"X-Aibo-API-Key": "test-secret"})
    assert session.status_code == 200

    status = client.get("/v1/status")
    assert status.status_code == 200


def test_session_endpoint_requires_bootstrap_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    response = client.post("/v1/session")
    assert response.status_code == 401


def test_invalid_bearer_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    response = client.get("/v1/status", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_phone_client_is_available():
    response = client.get("/app")
    assert response.status_code == 200
    assert "Aibo" in response.text
