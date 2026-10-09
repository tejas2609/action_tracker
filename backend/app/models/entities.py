import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Text,
    JSON,
    ForeignKey,
    DateTime,
    Integer,
    Date,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.core.security import EncryptedText


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    held_on: Mapped[datetime] = mapped_column(Date)
    transcript: Mapped[str] = mapped_column(EncryptedText())
    findings: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(30), default="draft")
    visibility: Mapped[str] = mapped_column(
        String(10),
        default="public",
        nullable=False,
        index=True,
    )


class Commitment(Base):
    __tablename__ = "commitments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(500))
    owner: Mapped[str] = mapped_column(String(120), index=True)
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    analysis_text: Mapped[str] = mapped_column(Text, default="")
    analysis_next: Mapped[str] = mapped_column(Text, default="")
    analysis_hash: Mapped[str] = mapped_column(String(64), default="")
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    condition: Mapped[str] = mapped_column(Text, default="")
    condition_met: Mapped[bool] = mapped_column(default=False)
    blocker: Mapped[str] = mapped_column(Text, default="")
    source_statement: Mapped[str] = mapped_column(Text)
    meeting_id: Mapped[str | None] = mapped_column(
        ForeignKey("meetings.id"),
        nullable=True,
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=now,
        server_default=func.now(),
    )


class Dependency(Base):
    __tablename__ = "dependencies"
    commitment_id: Mapped[str] = mapped_column(
        ForeignKey("commitments.id"), primary_key=True
    )
    prerequisite_id: Mapped[str] = mapped_column(
        ForeignKey("commitments.id"), primary_key=True
    )


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    commitment_id: Mapped[str] = mapped_column(ForeignKey("commitments.id"), index=True)
    meeting_id: Mapped[str | None] = mapped_column(
        ForeignKey("meetings.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


Index("ix_events_commitment_created", Event.commitment_id, Event.created_at)
Index("ix_dependencies_prerequisite", Dependency.prerequisite_id)
Index(
    "ix_commitments_org_owner_status",
    Commitment.organization_id,
    Commitment.owner_id,
    Commitment.status,
)


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"

    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )


class MeetingAccessRequest(Base):
    __tablename__ = "meeting_access_requests"

    __table_args__ = (
        UniqueConstraint(
            "meeting_id",
            "requester_id",
            name="uq_meeting_access_request",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=uid,
    )

    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        index=True,
    )

    requester_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    decided_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
