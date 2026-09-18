from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True
