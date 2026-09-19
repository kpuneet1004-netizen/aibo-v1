from dataclasses import dataclass

from app.services.capabilities import CapabilityDefinition

# Risk is deliberately monotonic: low-risk/read-only work can run autonomously,
# while consequential capabilities must cross an explicit approval boundary.
AUTO_ALLOWED_RISKS = frozenset({"low", "external_read"})
APPROVAL_RISKS = frozenset({"medium", "high", "critical", "external_write"})
KNOWN_RISKS = AUTO_ALLOWED_RISKS | APPROVAL_RISKS

@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    reason: str | None = None

class PermissionPolicy:
    def requires_approval(self, definition: CapabilityDefinition) -> bool:
        if definition.risk not in KNOWN_RISKS:
            return True
        return definition.requires_approval or definition.risk in APPROVAL_RISKS

    def evaluate(
        self,
        *,
        definition: CapabilityDefinition,
        approval_granted: bool = False,
    ) -> PermissionDecision:
        if definition.risk not in KNOWN_RISKS:
            return PermissionDecision(
                False,
                True,
                f"Capability '{definition.name}' uses an unknown risk class: {definition.risk}",
            )

        needs_approval = self.requires_approval(definition)
        if needs_approval and not approval_granted:
            return PermissionDecision(
                False,
                True,
                f"Capability '{definition.name}' requires user approval",
            )
        return PermissionDecision(True, needs_approval)

permission_policy = PermissionPolicy()
