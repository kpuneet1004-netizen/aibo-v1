from datetime import datetime, timezone

from pydantic import BaseModel, Field


class AiboEvent(BaseModel):
    type: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
