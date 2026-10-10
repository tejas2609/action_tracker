import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models.entities import now, uid
from app.models.notifications import Notification
from app.models.people import LoginSession, User


def notify(
    db,
    *,
    organization_id,
    recipient_id,
    kind,
    title,
    event_key,
    peer_id=None,
    commitment_id=None,
):
    recipient = db.get(User, recipient_id)

    if (
        not recipient
        or not recipient.active
        or recipient.organization_id != organization_id
    ):
        return

    # Atomic deduplication, including concurrent processing.
    db.execute(
        insert(Notification)
        .values(
            id=uid(),
            organization_id=organization_id,
            recipient_id=recipient_id,
            kind=kind,
            title=title[:600],
            event_key=event_key,
            peer_id=peer_id,
            commitment_id=commitment_id,
            created_at=now(),
        )
        .on_conflict_do_nothing(constraint="uq_notifications_recipient_event")
    )


def notify_commitment(db, commitment):
    if not commitment.owner_id:
        return

    review = commitment.status == "review"
    kind = "commitment_review" if review else "commitment_created"

    notify(
        db,
        organization_id=commitment.organization_id,
        recipient_id=commitment.owner_id,
        kind=kind,
        title=("Commitment needs review: " if review else "New commitment: ")
        + commitment.title,
        event_key=f"{kind}:{commitment.id}",
        commitment_id=commitment.id,
    )


def authenticate_socket(token):
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with SessionLocal() as db:
        session = db.get(LoginSession, token_hash)

        if not session:
            return None

        expiry = session.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if expiry <= datetime.now(timezone.utc):
            return None

        user = db.get(User, session.user_id)

        if not user or not user.active:
            return None

        return user.organization_id, user.id, expiry


def notification_snapshot(organization_id, recipient_id):
    # Short DB session, never held open for the WebSocket lifetime.
    with SessionLocal() as db:
        return saved_notifications(db, organization_id, recipient_id)


def saved_notifications(db, organization_id, recipient_id):
    scope = (
        Notification.organization_id == organization_id,
        Notification.recipient_id == recipient_id,
    )

    unread = db.scalar(
        select(func.count(Notification.id)).where(
            *scope,
            Notification.read_at.is_(None),
        )
    )

    rows = db.scalars(
        select(Notification)
        .where(*scope)
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(50)
    )

    return {
        "type": "notifications",
        "unread_count": unread or 0,
        "items": [
            {
                "id": row.id,
                "kind": row.kind,
                "title": row.title,
                "peer_id": row.peer_id,
                "commitment_id": row.commitment_id,
                "created_at": row.created_at.isoformat(),
                "read_at": (row.read_at.isoformat() if row.read_at else None),
            }
            for row in rows
        ],
    }
