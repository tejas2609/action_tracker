from app.schemas.base import StrictModel
from typing import Annotated
from datetime import datetime
from pydantic import (
    Field,
    ConfigDict,
    StringConstraints,
)


class BaseModel(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AttachmentMetadata(BaseModel):
    id: str
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=0)
    uploaded_by: str
    created_at: datetime


class Login(BaseModel):
    user_id: str


class PasswordLogin(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        min_length=1, max_length=200
    )


class MessageInput(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    commitment_id: str | None = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=0)
