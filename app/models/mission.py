from datetime import datetime, timezone
from uuid import uuid4
from enum import StrEnum
from pydantic import BaseModel, Field

class MissionStatus(StrEnum):
    PENDING="pending"
    PLANNING="planning"
    WAITING_APPROVAL="waiting_approval"
    RUNNING="running"
    COMPLETED="completed"
    FAILED="failed"
    CANCELLED="cancelled"

class Mission(BaseModel):
    id: str
    objective: str = Field(min_length=1)
    status: MissionStatus = MissionStatus.PENDING
    attempts: int = 0
    max_retries: int = Field(default=3, ge=0)
    plan: list[dict] | None = None
    result: dict | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MissionCreate(BaseModel):
    objective: str = Field(min_length=1)
    max_retries: int = Field(default=3, ge=0)

def new_mission(objective: str, max_retries: int = 3) -> Mission:
    return Mission(id=str(uuid4()), objective=objective, max_retries=max_retries)
