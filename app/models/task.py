from enum import StrEnum
from pydantic import BaseModel, Field

class TaskStatus(StrEnum):
    QUEUED="queued"; RUNNING="running"; COMPLETED="completed"; FAILED="failed"

class MissionTask(BaseModel):
    id: str
    mission_id: str
    agent: str
    action: str
    payload: dict = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.QUEUED
    attempts: int = 0
    max_retries: int = Field(default=3, ge=0)
    result: dict | None = None
    error: str | None = None
