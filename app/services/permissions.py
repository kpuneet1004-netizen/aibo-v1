from dataclasses import dataclass

from app.services.capabilities import CapabilityDefinition

@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    reason: str | None = None

class PermissionPolicy:
    def evaluate(
        self,
        *,
        definition: CapabilityDefinition,
        approval_granted: bool = False,
    ) -> PermissionDecision:
        if definition.requires_approval and not approval_granted:
            return PermissionDecision(
                False,
                True,
                f"Capability '{definition.name}' requires user approval",
            )
        return PermissionDecision(True, False)

permission_policy = PermissionPolicy()
