from fastapi.testclient import TestClient
import pytest

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


def test_health_reports_misconfigured_auth_in_production_without_key(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "api_key", "")
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["auth_configured"] is False
    assert body["status"] == "misconfigured"


def test_health_ok_in_production_with_key_configured(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "api_key", "test-secret")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["auth_configured"] is True


def test_require_safe_startup_raises_outside_dev_test_without_key(monkeypatch):
    from app.api import require_safe_startup
    from app.core.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "api_key", "")
    with pytest.raises(RuntimeError, match="Refusing to start"):
        require_safe_startup()


def test_require_safe_startup_allows_dev_and_test_without_key(monkeypatch):
    from app.api import require_safe_startup
    from app.core.config import settings
    monkeypatch.setattr(settings, "api_key", "")
    for env in ("development", "test"):
        monkeypatch.setattr(settings, "app_env", env)
        require_safe_startup()


def test_require_safe_startup_allows_production_with_key(monkeypatch):
    from app.api import require_safe_startup
    from app.core.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "api_key", "test-secret")
    require_safe_startup()


def test_settings_reads_documented_aibo_api_key_env_var(monkeypatch):
    from app.core.config import Settings
    monkeypatch.setenv("AIBO_API_KEY", "from-documented-env-var")
    assert Settings().api_key == "from-documented-env-var"
