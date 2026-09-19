from collections.abc import Callable
from typing import Any
from app.services.llm import llm_client

Handler = Callable[[dict[str, Any]], dict[str, Any]]

class CapabilityRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str, handler: Handler) -> None:
        self._handlers[name] = handler

    def get(self, name: str) -> Handler | None:
        return self._handlers.get(name)

    def names(self) -> list[str]:
        return sorted(self._handlers)

def respond_with_llm(payload: dict[str, Any]) -> dict[str, Any]:
    objective = str(payload.get("objective", "")).strip()
    if not objective:
        raise ValueError("objective is required")
    return llm_client.generate(objective)

def execute_with_llm(payload: dict[str, Any]) -> dict[str, Any]:
    return respond_with_llm(payload)

capability_registry = CapabilityRegistry()
capability_registry.register("respond", respond_with_llm)
capability_registry.register("execute", execute_with_llm)
