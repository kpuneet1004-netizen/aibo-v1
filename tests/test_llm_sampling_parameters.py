from app.core.config import settings
from app.services.llm import LLMClient


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "A real response"}}]}


def _capture_payload(monkeypatch, model):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["payload"] = json
        return FakeResponse()

    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_base_url", "https://provider.example/v1")
    monkeypatch.setattr(settings, "llm_model", model)
    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)

    assert LLMClient()._request("system", "user") == "A real response"
    return captured["payload"]


def test_gpt5_models_omit_temperature_override(monkeypatch):
    payload = _capture_payload(monkeypatch, "gpt-5-mini")

    assert payload["model"] == "gpt-5-mini"
    assert "temperature" not in payload


def test_other_models_keep_low_temperature(monkeypatch):
    payload = _capture_payload(monkeypatch, "gpt-4.1-mini")

    assert payload["temperature"] == 0.1
