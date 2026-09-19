from typing import Any
import json
import httpx
from app.core.config import settings

SYSTEM_PROMPT = """You are Aibo, a personal AI assistant.
Reason about the user objective, but never claim an external action happened unless the runtime actually executed and verified it.
"""

PLANNER_PROMPT = """You are Aibo's planning engine.
Return ONLY valid JSON with this shape:
{"steps":[{"id":"step-1","objective":"...","capability":"respond","agent":"general","payload":{"objective":"..."},"requires_approval":false,"depends_on":[]}]}
Create the smallest useful sequence of steps needed to accomplish the objective.
Use only capabilities and agents listed in the runtime contract.
Use depends_on to express prerequisites by step id. Independent steps may use an empty list.
Set requires_approval=true when a step requires explicit user authorization because it is sensitive, irreversible, personal, financial, security-sensitive, or externally consequential.
Do not claim execution; this is only a plan.
"""

class LLMError(RuntimeError):
    pass

class LLMClient:
    def _request(self, system: str, user: str) -> str:
        provider = settings.llm_provider.lower().strip()
        if provider == "stub":
            return ""
        if provider not in {"openai", "openai_compatible"}:
            raise LLMError(f"Unsupported LLM provider: {settings.llm_provider}")
        if not settings.llm_api_key:
            raise LLMError("LLM API key is not configured")
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {"model": settings.llm_model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.1}
        try:
            response = httpx.post(url, headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

    def generate(self, objective: str) -> dict[str, Any]:
        provider = settings.llm_provider.lower().strip()
        if provider == "stub":
            return {"provider": "stub", "model": "deterministic-test", "text": f"Aibo received the objective and prepared it for execution: {objective}"}
        text = self._request(SYSTEM_PROMPT, objective)
        return {"provider": provider, "model": settings.llm_model, "text": text}

    def plan(self, objective: str, runtime_contract: str | None = None) -> dict[str, Any]:
        provider = settings.llm_provider.lower().strip()
        if provider == "stub":
            return {"steps": [{"id": "step-1", "objective": objective, "capability": "respond", "agent": "general", "payload": {"objective": objective}, "requires_approval": False, "depends_on": []}]}
        user_prompt = objective
        if runtime_contract:
            user_prompt = f"{objective}\n\nRUNTIME CONTRACT:\n{runtime_contract}"
        text = self._request(PLANNER_PROMPT, user_prompt).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            data = json.loads(text)
            if not isinstance(data, dict) or not isinstance(data.get("steps"), list) or not data["steps"]:
                raise ValueError("planner returned no steps")
            return data
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LLMError(f"Planner returned invalid JSON: {exc}") from exc

llm_client = LLMClient()
