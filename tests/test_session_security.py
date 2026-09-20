import base64
import hashlib
import hmac
import json
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
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    storage.revoke_session(payload["nonce"], payload["exp"], int(time.time()))

    assert _valid_session(token) is False
    assert storage.is_session_revoked(payload["nonce"]) is True


def test_expired_session_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-session-key")
    token = _encode_session(int(time.time()) - 1)
    assert _valid_session(token) is False


def test_session_signature_is_domain_separated_from_api_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-session-key")
    expiry = int(time.time()) + 300
    payload = {"exp": expiry, "nonce": "fixed-test-nonce"}
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")

    api_key_signature = hmac.new(
        settings.api_key.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    legacy_style_token = f"{body}.{api_key_signature}"

    assert _valid_session(legacy_style_token) is False
    assert _valid_session(_encode_session(expiry)) is True
