"""Transport-neutral, validated source contract for future adapters."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=255)
    name: str = Field(max_length=255)
    email: str = Field(default="", max_length=255)


class ContextMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sender_id: str = Field(max_length=255)
    body: str = Field(max_length=1500)
    sent_at: datetime


class SourceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(default="", max_length=500)
    thread_id: str = Field(default="", max_length=255)
    sender: Identity
    recipient: Identity
    sent_at: datetime
    timezone: str = "UTC"
    body: str = Field(min_length=1, max_length=12000)
    context: list[ContextMessage] = Field(default_factory=list, max_length=8)
    commitment_id: str | None = None
    google_sub: str | None = None
    external_url: str | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Invalid timezone")
        return value
