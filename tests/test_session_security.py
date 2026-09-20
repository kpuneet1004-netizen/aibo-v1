import time

from app.api import _encode_session, _valid_session
from app.core.config import settings
from app.services.storage import storage


def test_session_is_valid_before_revocation(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-session-key")
    token = _encode_session(int(time.time()) + 300)
    assert _valid_session(token) is True


def test_revoked_session_is_rejected_after_persistence(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-session-key")
    token = _encode_session(int(time.time()) + 300)
    assert _valid_session(token) is True

    body = token.split(".", 1)[0]
    import base64
    import json
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    storage.revoke_session(payload["nonce"], payload["exp"], int(time.time()))

    assert _valid_session(token) is False
    assert storage.is_session_revoked(payload["nonce"]) is True


def test_expired_session_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-session-key")
    token = _encode_session(int(time.time()) - 1)
    assert _valid_session(token) is False
