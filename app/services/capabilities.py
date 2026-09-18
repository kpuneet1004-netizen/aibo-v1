from collections.abc import Callable
from typing import Any

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

capability_registry = CapabilityRegistry()

def execute_placeholder(payload: dict[str, Any]) -> dict[str, Any]:
    objective = payload.get("objective", "")
    return {"accepted": True, "objective": objective}

capability_registry.register("execute", execute_placeholder)
