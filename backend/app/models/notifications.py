from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.entities import now, uid


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        UniqueConstraint(
            "recipient_id",
            "event_key",
            name="uq_notifications_recipient_event",
        ),
        Index(
            "ix_notifications_recipient_created",
            "recipient_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_notifications_recipient_read",
            "recipient_id",
            "read_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    recipient_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )

    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(600))
    event_key: Mapped[str] = mapped_column(String(150))

    peer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    commitment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
