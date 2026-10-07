from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.entities import uid, now


class EmailSyncState(Base):
    __tablename__ = "email_sync_states"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    google_sub: Mapped[str] = mapped_column(String(255))

    history_id: Mapped[str] = mapped_column(String(100))
    history_page: Mapped[str | None] = mapped_column(Text, nullable=True)

    bootstrap_done: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    bootstrap_after: Mapped[int] = mapped_column(BigInteger)
    bootstrap_before: Mapped[int] = mapped_column(BigInteger)

    bootstrap_page: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_history_sync: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )


class EmailProcessing(Base):
    """Stores IDs and outcomes, never the mailbox message body."""

    __tablename__ = "email_processing"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    google_sub: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    message_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    state: Mapped[str] = mapped_column(
        String(30),
        default="queued",
        index=True,
    )


class EmailOrigin(Base):
    """Metadata identifying the email behind a proposed commitment."""

    __tablename__ = "email_origins"

    commitment_id: Mapped[str] = mapped_column(
        ForeignKey("commitments.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    google_sub: Mapped[str] = mapped_column(String(255))
    message_id: Mapped[str] = mapped_column(String(255))
    thread_id: Mapped[str] = mapped_column(String(255))

    subject: Mapped[str] = mapped_column(String(1000))
    sender: Mapped[str] = mapped_column(String(1000))

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    description: Mapped[str] = mapped_column(Text)


class CommitmentEmail(Base):
    __tablename__ = "commitment_emails"

    __table_args__ = (
        UniqueConstraint(
            "commitment_id",
            "user_id",
            "google_sub",
            "message_id",
            name="uq_commitment_email",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=uid,
    )

    commitment_id: Mapped[str] = mapped_column(
        ForeignKey("commitments.id", ondelete="CASCADE"),
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    google_sub: Mapped[str] = mapped_column(String(255))

    message_id: Mapped[str] = mapped_column(String(255))
    thread_id: Mapped[str] = mapped_column(String(255))

    subject: Mapped[str] = mapped_column(String(1000))
    sender: Mapped[str] = mapped_column(String(1000))

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    description: Mapped[str] = mapped_column(Text)

    body_text: Mapped[str] = mapped_column(Text)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )
