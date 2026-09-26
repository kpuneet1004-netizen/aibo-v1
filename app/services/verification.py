from typing import Any
from app.services.capabilities import capability_registry

class VerificationError(RuntimeError):
    pass

class Verifier:
    def verify(self, capability: str, result: Any) -> dict:
        if result is None:
            raise VerificationError("Capability returned no result")
        if not isinstance(result, dict):
            raise VerificationError("Capability returned a non-object result")
        definition = capability_registry.definition(capability)
        if definition is None:
            raise VerificationError(f"Capability unavailable: {capability}")
        if definition.verify is None:
            raise VerificationError(f"No verification contract for capability: {capability}")
        try:
            definition.verify(result)
        except VerificationError:
            raise
        except Exception as exc:
            raise VerificationError(str(exc)) from exc
        return {"verified": True}

verifier = Verifier()
