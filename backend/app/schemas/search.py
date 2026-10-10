from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal[
        "tasks",
        "overview",
        "compare",
        "priorities",
        "prerequisites",
        "impact",
        "meeting_status",
        "unsupported",
    ] = "tasks"

    owner_names: list[str] = Field(default_factory=list, max_length=10)
    owner_is_me: bool = False

    meeting_title: str | None = Field(default=None, max_length=200)

    statuses: list[Literal["active", "completed", "cancelled"]] = Field(
        default_factory=list, max_length=3
    )

    risk_levels: list[Literal["low", "medium", "high"]] = Field(
        default_factory=list, max_length=3
    )

    due_from: date | None = None
    due_to: date | None = None
    missing_deadline: bool | None = None
    overdue: bool | None = None
    blocked: bool | None = None

    progress_min: int | None = Field(default=None, ge=0, le=100)
    progress_max: int | None = Field(default=None, ge=0, le=100)

    # Meaning-based requirements that cannot be safely represented
    # by the structured fields above.
    semantic_requirement: str | None = Field(
        default=None,
        max_length=1500,
    )

    sort: Literal[
        "priority",
        "due_date",
        "progress",
        "title",
    ] = "priority"

    descending: bool = False

    unsupported_reason: str | None = Field(
        default=None,
        max_length=500,
    )


class SelectedRecords(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matching_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
    )
