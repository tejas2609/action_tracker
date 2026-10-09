from datetime import date
from app.schemas.base import StrictModel as BaseModel
from pydantic import Field, field_validator


class AcceptProposal(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        value = value.strip()

        if len(value) < 3:
            raise ValueError("Enter a title of at least three characters.")

        return value
