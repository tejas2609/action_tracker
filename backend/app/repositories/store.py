from fastapi import HTTPException
from sqlalchemy import select

from app.models.entities import Commitment, Meeting, Dependency, Event
from app.services.meetings.meeting_access_policy import (
    readable_condition,
    require_read,
)


class Store:
    def __init__(self, db, actor=None):
        self.db = db
        self.actor = actor

    def all(self, model, limit=None):
        query = select(model)

        if self.actor:
            organization_id = self.actor.organization_id

            if model is Meeting:
                query = query.where(
                    readable_condition(self.actor),
                )

            elif model is Commitment:
                query = query.where(
                    Commitment.organization_id == organization_id,
                    Commitment.status != "review",
                )

            elif model is Dependency:
                query = query.join(
                    Commitment,
                    Dependency.commitment_id == Commitment.id,
                ).where(
                    Commitment.organization_id == organization_id,
                    Commitment.status != "review",
                )

            elif model is Event:
                query = query.join(
                    Commitment,
                    Event.commitment_id == Commitment.id,
                ).where(
                    Commitment.organization_id == organization_id,
                    Commitment.status != "review",
                )

        if limit is not None:
            query = query.limit(limit)
        return list(self.db.scalars(query))

    def get(self, model, id):
        if model is Meeting and self.actor:
            return require_read(
                self.db,
                self.actor,
                id,
            )
        row = self.db.get(model, id)

        if row is None:
            raise HTTPException(404, "Record not found")

        if self.actor:
            organization_id = self.actor.organization_id

            if model is Meeting:
                allowed = row.organization_id == organization_id

            elif model is Commitment:
                allowed = (
                    row.organization_id == organization_id and row.status != "review"
                )

            elif model in (Event, Dependency):
                commitment = self.db.get(
                    Commitment,
                    row.commitment_id,
                )

                allowed = bool(
                    commitment
                    and commitment.organization_id == organization_id
                    and commitment.status != "review"
                )

            else:
                allowed = True

            if not allowed:
                raise HTTPException(404, "Record not found")

        return row

    def events_for(self, commitment_id):
        self.get(Commitment, commitment_id)
        return list(
            self.db.scalars(
                select(Event)
                .where(Event.commitment_id == commitment_id)
                .order_by(Event.created_at.desc(), Event.id.desc())
                .limit(200)
            )
        )

    def event(self, c, kind, message, meeting_id=None):
        self.db.add(
            Event(
                commitment_id=c.id,
                kind=kind,
                message=message,
                meeting_id=meeting_id,
            )
        )

    def save(self, row):
        if isinstance(row, Commitment) and not row.organization_id:
            if self.actor:
                row.organization_id = self.actor.organization_id
            elif row.meeting_id:
                meeting = self.db.get(Meeting, row.meeting_id)

                if meeting:
                    row.organization_id = meeting.organization_id

            if not row.organization_id:
                raise HTTPException(
                    422,
                    "Commitment requires an organization.",
                )

        self.db.add(row)
        self.db.flush()

        return row
