from app.schemas.base import StrictModel as BaseModel
from pydantic import Field


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200)
