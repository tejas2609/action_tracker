from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class MeetingInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    held_on: date
    transcript: str = Field(min_length=10, max_length=60000)

    visibility: Literal["public", "private"] = "public"

    participant_ids: list[str] = Field(
        default_factory=list,
        max_length=200,
    )


class ManualCommitmentInput(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=10000)
    due_date: date | None = None
    progress: int = Field(default=0, ge=0, le=100)
    condition: str = Field(default="", max_length=2000)
    condition_met: bool = False
    blocker: str = Field(default="", max_length=2000)
    meeting_id: str | None = Field(default=None, max_length=36)
    prerequisite_ids: list[str] = Field(default_factory=list, max_length=30)


class Finding(BaseModel):
    kind: Literal[
        "commitment", "request", "decision", "suggestion", "discussion", "hypothetical"
    ]
    title: str = Field(min_length=1, max_length=500)
    owner: str = Field(default="", max_length=120)
    source_line: int | None = Field(default=None, ge=1)
    statement: str = Field(default="source", min_length=1)
    due_date: date | None = None
    condition: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    explanation: str = ""
    existing_id: str | None = None
    depends_on_indices: list[int] = Field(default_factory=list, max_length=30)
    prerequisite_ids: list[str] = Field(default_factory=list, max_length=30)


class Findings(BaseModel):
    findings: list[Finding] = Field(max_length=100)


class ReviewItem(BaseModel):
    index: int = Field(ge=0)
    owner_id: str | None = None
    action: Literal["confirm", "ignore", "link"]
    title: str = Field(min_length=1, max_length=500)
    owner: str = Field(min_length=1, max_length=120)
    due_date: date | None = None
    condition: str = ""
    existing_id: str | None = None
    depends_on_indices: list[int] = Field(default_factory=list, max_length=30)
    prerequisite_ids: list[str] = Field(default_factory=list, max_length=30)


class Review(BaseModel):
    items: list[ReviewItem] = Field(max_length=100)


class Update(BaseModel):
    owner_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    owner: str | None = Field(default=None, min_length=1, max_length=120)
    due_date: date | None = None
    status: Literal["active", "completed", "cancelled"] | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    condition: str | None = None
    condition_met: bool | None = None
    blocker: str | None = None


class EdgeInput(BaseModel):
    prerequisite_id: str


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


class FollowupInput(BaseModel):
    recipient_id: str | None = None
