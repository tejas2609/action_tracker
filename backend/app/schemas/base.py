from pydantic import BaseModel, ConfigDict, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def reserved_prefix(self):
        from app.core.config import settings

        if not settings.data_encryption_keys:
            for field in ("body", "transcript"):
                value = getattr(self, field, None)
                if isinstance(value, str) and value.startswith("enc:v1:"):
                    raise ValueError("Reserved content prefix")
        return self
