from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.entities import now, uid


class SourceInbox(Base):
    __tablename__ = "source_inbox"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_id",
            "recipient_id",
            name="uq_source_recipient_message",
        ),
        Index(
            "ix_source_inbox_pending",
            "state",
            "available_at",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=uid,
    )

    source: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(255))

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )

    recipient_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    payload: Mapped[dict] = mapped_column(JSON)

    state: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(String(120), default="")

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )


class CommitmentSource(Base):
    __tablename__ = "commitment_sources"

    __table_args__ = (
        UniqueConstraint(
            "inbox_id",
            "commitment_id",
            name="uq_source_commitment",
        ),
        Index(
            "ix_commitment_sources_commitment",
            "commitment_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=uid,
    )

    inbox_id: Mapped[str] = mapped_column(
        ForeignKey("source_inbox.id", ondelete="CASCADE"),
    )

    commitment_id: Mapped[str] = mapped_column(
        ForeignKey("commitments.id", ondelete="CASCADE"),
    )

    # proposal or related
    kind: Mapped[str] = mapped_column(String(20))

    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )
