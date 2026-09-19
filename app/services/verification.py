from typing import Any

class VerificationError(RuntimeError):
    pass

class Verifier:
    def verify(self, result: Any) -> dict:
        if result is None:
            raise VerificationError("Capability returned no result")
        if isinstance(result, dict):
            if result.get("verified") is False:
                raise VerificationError(result.get("reason") or "Capability reported failure")
            if "text" in result and not str(result["text"]).strip():
                raise VerificationError("Capability returned empty text")
        return {"verified": True}

verifier = Verifier()
