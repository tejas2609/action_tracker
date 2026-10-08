from fastapi import HTTPException
from sqlalchemy import select, exists, and_, or_, false

from app.models.entities import (
    Meeting,
    MeetingParticipant,
    MeetingAccessRequest,
)
from app.models.people import User


def participant_condition(actor, meeting=Meeting):
    return exists(
        select(MeetingParticipant.meeting_id)
        .where(
            MeetingParticipant.meeting_id == meeting.id,
            MeetingParticipant.user_id == actor.id,
        )
        .correlate(meeting)
    )


def manager_condition(actor, meeting=Meeting):
    if not actor.is_manager:
        return false()

    return exists(
        select(MeetingParticipant.meeting_id)
        .join(
            User,
            User.id == MeetingParticipant.user_id,
        )
        .where(
            MeetingParticipant.meeting_id == meeting.id,
            User.organization_id == actor.organization_id,
            User.manager_id == actor.id,
        )
        .correlate(meeting)
    )


def approved_condition(actor, meeting=Meeting):
    return and_(
        meeting.visibility == "public",
        exists(
            select(MeetingAccessRequest.id)
            .where(
                MeetingAccessRequest.meeting_id == meeting.id,
                MeetingAccessRequest.requester_id == actor.id,
                MeetingAccessRequest.status == "approved",
            )
            .correlate(meeting)
        ),
    )


def readable_condition(actor, meeting=Meeting):
    return and_(
        meeting.organization_id == actor.organization_id,
        or_(
            participant_condition(actor, meeting),
            manager_condition(actor, meeting),
            approved_condition(actor, meeting),
        ),
    )


def require_read(db, actor, meeting_id):
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
            readable_condition(actor),
        )
    )

    if meeting is None:
        raise HTTPException(404, "Meeting not found")

    return meeting


def require_workflow_access(db, actor, meeting_id):
    # Participants and responsible managers use the existing
    # analysis/review workflow. Approved requesters get read access.
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.organization_id == actor.organization_id,
            or_(
                participant_condition(actor),
                manager_condition(actor),
            ),
        )
    )

    if meeting is None:
        raise HTTPException(404, "Meeting not found")

    return meeting


def require_manager(db, actor, meeting_id):
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.organization_id == actor.organization_id,
            manager_condition(actor),
        )
    )

    if meeting is None:
        raise HTTPException(
            404,
            "Meeting not found or you do not manage its participants",
        )

    return meeting


def responsible_managers(db, organization_id, meeting_id):
    participant = User.__table__.alias("participant")
    manager = User.__table__.alias("manager")

    rows = db.execute(
        select(manager.c.id, manager.c.name)
        .select_from(MeetingParticipant)
        .join(
            participant,
            participant.c.id == MeetingParticipant.user_id,
        )
        .join(
            manager,
            manager.c.id == participant.c.manager_id,
        )
        .where(
            MeetingParticipant.meeting_id == meeting_id,
            participant.c.organization_id == organization_id,
            manager.c.organization_id == organization_id,
            manager.c.is_manager.is_(True),
            manager.c.active.is_(True),
        )
        .distinct()
        .order_by(manager.c.name, manager.c.id)
    )

    return [{"id": row.id, "name": row.name} for row in rows]
