from dataclasses import dataclass

@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    reason: str | None = None

class PermissionPolicy:
    def evaluate(self, *, requires_approval: bool, capability: str) -> PermissionDecision:
        if requires_approval:
            return PermissionDecision(False, True, f"Capability '{capability}' requires user approval")
        return PermissionDecision(True, False)

permission_policy = PermissionPolicy()
