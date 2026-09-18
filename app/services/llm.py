from typing import Any
import httpx
from app.core.config import settings

SYSTEM_PROMPT = """You are Aibo, a personal AI assistant.
Be concise, practical, and objective-oriented. Turn the user's objective into useful next actions or an answer.
Do not claim an action was completed unless the tool/runtime actually completed it."""

class LLMError(RuntimeError):
    pass

class LLMClient:
    def generate(self, objective: str) -> dict[str, Any]:
        provider = settings.llm_provider.lower().strip()
        if provider == "stub":
            return {"provider": "stub", "model": "deterministic-test", "text": f"Aibo received the objective and prepared it for execution: {objective}"}
        if provider not in {"openai", "openai_compatible"}:
            raise LLMError(f"Unsupported LLM provider: {settings.llm_provider}")
        if not settings.llm_api_key:
            raise LLMError("LLM API key is not configured")
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {"model": settings.llm_model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": objective}], "temperature": 0.2}
        try:
            response = httpx.post(url, headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            return {"provider": provider, "model": settings.llm_model, "text": data["choices"][0]["message"]["content"]}
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

llm_client = LLMClient()
