from datetime import date

from fastapi import HTTPException, Response
from app.schemas.base import StrictModel as BaseModel
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Commitment, Event
from app.models.people import User
from app.models.source_actions import CommitmentSource, SourceInbox


class AcceptSource(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    due_date: date | None = None


def own_commitment(db, actor, commitment_id, lock=False):
    query = select(Commitment).where(
        Commitment.id == commitment_id,
        Commitment.owner_id == actor.id,
        Commitment.organization_id == actor.organization_id,
    )

    if lock:
        query = query.with_for_update()

    commitment = db.scalar(query)

    if not commitment:
        raise HTTPException(404, "Commitment not found")

    return commitment


def source_query(actor):
    return (
        select(CommitmentSource, SourceInbox)
        .join(
            SourceInbox,
            SourceInbox.id == CommitmentSource.inbox_id,
        )
        .where(
            SourceInbox.recipient_id == actor.id,
            SourceInbox.organization_id == actor.organization_id,
        )
    )


def source_dict(link, inbox):
    payload = inbox.payload

    return {
        "id": link.id,
        "source": inbox.source,
        "kind": link.kind,
        "message_id": inbox.external_id,
        "sender": payload["sender"]["name"],
        "received_at": payload["sent_at"],
        "description": link.description,
        "proposed_changes": link.proposed_changes,
        "evidence": link.evidence,
        "body_text": payload["body"],
    }


def require_proposal(db, actor, commitment_id):
    commitment = own_commitment(
        db,
        actor,
        commitment_id,
        lock=True,
    )

    if commitment.status != "review":
        raise HTTPException(409, "Proposal already reviewed")

    source = db.execute(
        source_query(actor).where(
            CommitmentSource.commitment_id == commitment.id,
            CommitmentSource.kind == "proposal",
        )
    ).first()

    if not source:
        raise HTTPException(404, "Source proposal not found")

    return commitment


def review(
    response: Response,
    page: int = 1,
    page_size: int = 10,
    actor: User = None,
    db: Session = None,
):
    response.headers["Cache-Control"] = "no-store"

    query = (
        select(Commitment, CommitmentSource, SourceInbox)
        .join(
            CommitmentSource,
            CommitmentSource.commitment_id == Commitment.id,
        )
        .join(
            SourceInbox,
            SourceInbox.id == CommitmentSource.inbox_id,
        )
        .where(
            Commitment.owner_id == actor.id,
            Commitment.organization_id == actor.organization_id,
            Commitment.status == "review",
            CommitmentSource.kind == "proposal",
            SourceInbox.recipient_id == actor.id,
            SourceInbox.organization_id == actor.organization_id,
        )
    )

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    rows = db.execute(
        query.order_by(
            CommitmentSource.created_at.desc(),
            CommitmentSource.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "items": [
            {
                **source_dict(link, inbox),
                "id": commitment.id,
                "title": commitment.title,
                "due_date": commitment.due_date,
            }
            for commitment, link, inbox in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def accept(
    id: str,
    body: AcceptSource,
    actor: User = None,
    db: Session = None,
):
    commitment = require_proposal(db, actor, id)
    title = body.title.strip()

    if len(title) < 3:
        raise HTTPException(
            422,
            "Title must contain at least three characters",
        )

    commitment.title = title
    commitment.due_date = body.due_date
    commitment.status = "active"

    db.add(
        Event(
            commitment_id=commitment.id,
            kind="created",
            message="Recipient accepted source proposal",
        )
    )

    db.commit()
    return {"id": commitment.id}


def reject(
    id: str,
    actor: User = None,
    db: Session = None,
):
    commitment = require_proposal(db, actor, id)

    # Retain source history and processing idempotency.
    commitment.status = "cancelled"

    db.add(
        Event(
            commitment_id=commitment.id,
            kind="cancelled",
            message="Recipient rejected source proposal",
        )
    )

    db.commit()
    return {"id": commitment.id}


def sources(
    id: str,
    response: Response,
    page: int = 1,
    page_size: int = 10,
    actor: User = None,
    db: Session = None,
):
    response.headers["Cache-Control"] = "no-store"

    own_commitment(db, actor, id)

    query = source_query(actor).where(
        CommitmentSource.commitment_id == id,
    )

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    rows = db.execute(
        query.order_by(
            CommitmentSource.created_at.desc(),
            CommitmentSource.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "items": [source_dict(link, inbox) for link, inbox in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def apply_update(link_id: str, actor: User = None, db: Session = None):
    """Apply a structured source suggestion only on the owner's explicit request."""
    row = db.execute(
        source_query(actor).where(CommitmentSource.id == link_id).with_for_update()
    ).first()
    if not row:
        raise HTTPException(404, "Source update not found")
    link, inbox = row
    commitment = own_commitment(db, actor, link.commitment_id, lock=True)
    if commitment.status != "active":
        raise HTTPException(409, "Only active commitments can be updated")
    from app.services.sources.shared_classifier import ProposedChanges

    changes = ProposedChanges.model_validate(link.proposed_changes).model_dump(
        exclude_unset=True
    )
    if not changes:
        raise HTTPException(409, "No pending structured changes")
    for field, value in changes.items():
        if value is None and field != "due_date":
            raise HTTPException(422, "Invalid null update")
        setattr(commitment, field, value)
    db.add(
        Event(
            commitment_id=commitment.id,
            kind="source_update_applied",
            message="Recipient approved source changes: " + ", ".join(changes),
        )
    )
    link.proposed_changes = {}
    db.commit()
    return {"id": commitment.id, "applied_fields": list(changes)}
