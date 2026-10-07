from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "find_commitments",
        "find_blockers",
        "find_prerequisites",
    ]
    owner_name: str | None = Field(default=None, max_length=120)
    owner_is_me: bool = False

    # Alternative phrases describing the same action.
    terms: list[str] = Field(default_factory=list, max_length=6)

    status: Literal["active", "completed", "cancelled"] | None = None
