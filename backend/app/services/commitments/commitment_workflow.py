from fastapi import HTTPException
from app.models.entities import Commitment, Meeting
from app.models.people import User
from sqlalchemy import select
from app.services.commitments.intelligence import serialize


class CommitmentWorkflow:
    def assign_meeting(self, id, meeting_id):
        from app.core.permissions import require_edit

        c = self.s.db.scalar(
            select(Commitment)
            .where(
                Commitment.id == id,
                Commitment.organization_id == self.s.actor.organization_id,
                Commitment.status != "review",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        require_edit(self.s.actor, c)
        if c.meeting_id:
            raise HTTPException(409, "This commitment already belongs to a meeting.")
        meeting = self.s.db.scalar(
            select(Meeting)
            .where(
                Meeting.id == meeting_id,
                Meeting.organization_id == self.s.actor.organization_id,
                Meeting.visibility == "public",
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if meeting is None:
            raise HTTPException(404, "Public meeting not found.")
        c.meeting_id = meeting.id
        self.s.event(
            c,
            "meeting_assigned",
            "Assigned to meeting: " + meeting.title,
            meeting_id=meeting.id,
        )
        self.s.db.commit()
        return {"id": c.id, "meeting_id": c.meeting_id}

    def update(self, id, patch):
        c = self.s.db.scalar(
            select(Commitment)
            .where(Commitment.id == id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        from app.core.permissions import require_edit

        require_edit(self.s.actor, c)
        before_levels = self.risk_levels([id])
        rows, edges = self.snapshot([id])
        values = patch.model_dump(exclude_unset=True)
        if self.s.actor and ("owner" in values or "owner_id" in values):
            owner_id = self.resolve_owner(
                values.get("owner") or c.owner, values.get("owner_id")
            )
            if not owner_id:
                raise HTTPException(422, "Select an organization user as owner.")
            values["owner_id"] = owner_id
            values["owner"] = self.s.db.get(User, owner_id).name
        for key, value in values.items():
            if value is None and key != "due_date":
                raise HTTPException(422, key + " cannot be null")
            if getattr(c, key) != value:
                self.s.event(
                    c,
                    (
                        "deadline_change"
                        if key == "due_date"
                        else "status_change"
                        if key == "status"
                        else "updated"
                    ),
                    f"{key}: {getattr(c, key)} → {value}",
                )
                setattr(c, key, value)
        if c.status == "completed":
            c.progress = 100
        self.audit_risks(before_levels)
        self.s.db.commit()
        return serialize(c, rows, edges)
