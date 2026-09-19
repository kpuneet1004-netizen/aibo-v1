from pydantic import BaseModel, Field

class PlanStep(BaseModel):
    id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    requires_approval: bool = False
    depends_on: list[str] = Field(default_factory=list)

class AgentPlan(BaseModel):
    objective: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1)
