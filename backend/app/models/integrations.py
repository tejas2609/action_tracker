from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GmailConnection(Base):
    __tablename__ = "gmail_connections"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    google_sub: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(255), default="")

    scopes: Mapped[str] = mapped_column(Text)

    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )


class GmailOAuthState(Base):
    __tablename__ = "gmail_oauth_states"

    state_hash: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    session_hash: Mapped[str] = mapped_column(String(64))
    browser_hash: Mapped[str] = mapped_column(String(64))

    verifier_encrypted: Mapped[str] = mapped_column(Text)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
