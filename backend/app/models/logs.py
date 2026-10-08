"""Operational logs contain metadata only, never tokens or request bodies."""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, DateTime, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class LogColumns:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    action: Mapped[str] = mapped_column(String(200))
    request_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[float] = mapped_column(Float)


class AuthLog(LogColumns, Base):
    __tablename__ = "auth_logs"


class GeneralLog(LogColumns, Base):
    __tablename__ = "general_logs"


class ErrorLog(LogColumns, Base):
    __tablename__ = "error_logs"
    error_type: Mapped[str] = mapped_column(String(100))
