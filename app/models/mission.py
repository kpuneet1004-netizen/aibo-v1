from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class MissionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Mission(BaseModel):
    id: str
    objective: str = Field(min_length=1)
    status: MissionStatus = MissionStatus.PENDING
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class MissionCreate(BaseModel):
    objective: str = Field(min_length=1)
