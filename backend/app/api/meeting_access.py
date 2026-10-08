from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.core.database import get_db
from app.models.people import User
from app.models.entities import (
    Meeting,
    MeetingAccessRequest,
)
from app.services.meeting_access_policy import (
    readable_condition,
    manager_condition,
    require_manager,
    responsible_managers,
)

router = APIRouter(
    prefix="/api",
    tags=["meeting-access"],
)


class AccessRequestInput(BaseModel):
    reason: str = Field(default="", max_length=2000)


class AccessDecisionInput(BaseModel):
    decision: Literal["approved", "rejected"]


@router.get("/meeting-directory")
def directory(
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    # Metadata only. Never include transcripts or findings.
    query = (
        select(
            Meeting.id,
            Meeting.title,
            Meeting.held_on,
            readable_condition(actor).label("can_access"),
            MeetingAccessRequest.status.label("request_status"),
        )
        .outerjoin(
            MeetingAccessRequest,
            (
                (MeetingAccessRequest.meeting_id == Meeting.id)
                & (MeetingAccessRequest.requester_id == actor.id)
            ),
        )
        .where(
            Meeting.organization_id == actor.organization_id,
            Meeting.visibility == "public",
        )
    )

    if q.strip():
        query = query.where(Meeting.title.icontains(q.strip(), autoescape=True))

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    rows = db.execute(
        query.order_by(Meeting.held_on.desc(), Meeting.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/meetings/{meeting_id}/access-requests",
    status_code=201,
)
def request_access(
    meeting_id: str,
    body: AccessRequestInput,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.organization_id == actor.organization_id,
            Meeting.visibility == "public",
        )
    )

    # Private meetings cannot be discovered or requested by ID.
    if meeting is None:
        raise HTTPException(404, "Meeting not found")

    already_allowed = db.scalar(
        select(Meeting.id).where(
            Meeting.id == meeting_id,
            readable_condition(actor),
        )
    )

    if already_allowed:
        raise HTTPException(409, "You already have meeting access")

    managers = responsible_managers(
        db,
        actor.organization_id,
        meeting_id,
    )

    if not managers:
        raise HTTPException(
            409,
            "No active participant manager is configured for this meeting.",
        )

    existing = db.scalar(
        select(MeetingAccessRequest).where(
            MeetingAccessRequest.meeting_id == meeting_id,
            MeetingAccessRequest.requester_id == actor.id,
        )
    )

    if existing:
        if existing.status != "rejected":
            raise HTTPException(
                409,
                f"An access request already exists: {existing.status}.",
            )

        existing.status = "pending"
        existing.reason = body.reason.strip()
        existing.created_at = datetime.now(timezone.utc)
        existing.decided_at = None
        existing.decided_by = None

        db.commit()

        return {
            "id": existing.id,
            "status": existing.status,
            "managers": managers,
        }

    request = MeetingAccessRequest(
        meeting_id=meeting_id,
        requester_id=actor.id,
        reason=body.reason.strip(),
        status="pending",
    )

    db.add(request)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "An access request already exists.",
        )

    return {
        "id": request.id,
        "status": request.status,
        "managers": managers,
    }


@router.get("/meeting-access-requests")
def manager_requests(
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    # Each responsible manager sees the same pending request.
    query = (
        select(
            MeetingAccessRequest.id,
            MeetingAccessRequest.reason,
            MeetingAccessRequest.created_at,
            Meeting.id.label("meeting_id"),
            Meeting.title.label("meeting_title"),
            User.name.label("requester_name"),
        )
        .join(
            Meeting,
            Meeting.id == MeetingAccessRequest.meeting_id,
        )
        .join(
            User,
            User.id == MeetingAccessRequest.requester_id,
        )
        .where(
            Meeting.organization_id == actor.organization_id,
            User.organization_id == actor.organization_id,
            Meeting.visibility == "public",
            MeetingAccessRequest.status == "pending",
            manager_condition(actor),
        )
    )

    if q.strip():
        query = query.where(
            or_(
                Meeting.title.icontains(q.strip(), autoescape=True),
                User.name.icontains(q.strip(), autoescape=True),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    rows = db.execute(
        query.order_by(
            MeetingAccessRequest.created_at,
            MeetingAccessRequest.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/meeting-access-requests/{request_id}/decision")
def decide_access(
    request_id: str,
    body: AccessDecisionInput,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    request = db.scalar(
        select(MeetingAccessRequest)
        .where(MeetingAccessRequest.id == request_id)
        .with_for_update()
    )

    if request is None:
        raise HTTPException(404, "Request not found")

    meeting = require_manager(
        db,
        actor,
        request.meeting_id,
    )

    if meeting.visibility != "public":
        raise HTTPException(
            409,
            "Private meetings cannot grant requested access.",
        )

    if request.status != "pending":
        raise HTTPException(
            409,
            "This request has already been decided.",
        )

    requester = db.get(User, request.requester_id)

    if (
        requester is None
        or not requester.active
        or requester.organization_id != actor.organization_id
    ):
        raise HTTPException(
            409,
            "The requester is no longer an active organization member.",
        )

    request.status = body.decision
    request.decided_by = actor.id
    request.decided_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "id": request.id,
        "status": request.status,
    }
