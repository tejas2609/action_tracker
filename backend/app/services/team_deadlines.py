from datetime import date

from fastapi import HTTPException
from sqlalchemy import select

from app.models.people import User


def team_missed_deadlines(
    workflow,
    page=1,
    page_size=10,
    q="",
    owner_id="",
    due_from=None,
    due_to=None,
    blocked="all",
    sort="due_date",
    direction="asc",
):
    """Only active direct reports in the actor's organization form their team."""
    actor = workflow.s.actor
    if not actor.is_manager:
        raise HTTPException(403, "Only managers can view team missed deadlines.")
    if due_from and due_to and due_from > due_to:
        raise HTTPException(422, "Deadline start must be on or before deadline end.")

    members = list(
        workflow.s.db.scalars(
            select(User)
            .where(
                User.organization_id == actor.organization_id,
                User.manager_id == actor.id,
                User.id != actor.id,
                User.active.is_(True),
            )
            .order_by(User.name, User.id)
        )
    )
    member_ids = {u.id for u in members}
    today = date.today()
    rows = [
        c
        for c in workflow.listing()
        if c["owner_id"] in member_ids
        and c["status"] == "active"
        and c["due_date"] is not None
        and c["due_date"] < today
        and (not owner_id or c["owner_id"] == owner_id)
        and q.strip().casefold() in (c["title"] + " " + c["owner"]).casefold()
        and (not due_from or c["due_date"] >= due_from)
        and (not due_to or c["due_date"] <= due_to)
        and (
            blocked == "all" or (c["risk"]["state"] == "waiting") == (blocked == "yes")
        )
    ]
    rows.sort(key=lambda c: c["id"])
    rows.sort(
        key=lambda c: c[sort].casefold() if isinstance(c[sort], str) else c[sort],
        reverse=direction == "desc",
    )
    total = len(rows)
    page = min(page, max(1, (total + page_size - 1) // page_size))
    start = (page - 1) * page_size
    return {
        "items": rows[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "members": [{"id": u.id, "name": u.name} for u in members],
    }
