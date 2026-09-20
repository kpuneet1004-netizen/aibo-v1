from enum import StrEnum
from pydantic import BaseModel, Field

class TaskStatus(StrEnum):
    QUEUED="queued"; WAITING_APPROVAL="waiting_approval"; RUNNING="running"; COMPLETED="completed"; FAILED="failed"

class MissionTask(BaseModel):
    id: str
    mission_id: str
    agent: str
    action: str
    payload: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    approval_granted: bool = False
    status: TaskStatus = TaskStatus.QUEUED
    attempts: int = 0
    max_retries: int = Field(default=3, ge=0)
    result: dict | None = None
    error: str | None = None
