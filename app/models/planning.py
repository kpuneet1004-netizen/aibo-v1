from pydantic import BaseModel, Field, field_validator


class PlanStep(BaseModel):
    id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    requires_approval: bool = False
    depends_on: list[str] = Field(default_factory=list)

    @field_validator("payload")
    @classmethod
    def reject_internal_payload_keys(cls, value: dict) -> dict:
        reserved = sorted(key for key in value if isinstance(key, str) and key.startswith("_"))
        if reserved:
            raise ValueError(
                "Plan payload contains reserved internal keys: " + ", ".join(reserved)
            )
        return value


class AgentPlan(BaseModel):
    objective: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1)
