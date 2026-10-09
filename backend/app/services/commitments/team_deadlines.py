from datetime import date

from fastapi import HTTPException
from sqlalchemy import select, func

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
    from app.repositories.commitments import CommitmentRepository
    from app.models.entities import Commitment
    from sqlalchemy import or_

    repo = CommitmentRepository(workflow.s.db, actor)
    member_ids = {u.id for u in members}
    query = repo.base().where(
        Commitment.owner_id.in_(member_ids),
        Commitment.status == "active",
        Commitment.due_date < date.today(),
    )
    if owner_id:
        query = query.where(Commitment.owner_id == owner_id)
    if q:
        query = query.where(
            or_(
                Commitment.title.ilike("%" + q.strip() + "%"),
                Commitment.owner.ilike("%" + q.strip() + "%"),
            )
        )
    if due_from:
        query = query.where(Commitment.due_date >= due_from)
    if due_to:
        query = query.where(Commitment.due_date <= due_to)
    if blocked != "all":
        query = query.where(repo.expressions()[0] == (blocked == "yes"))
    columns = {
        "due_date": Commitment.due_date,
        "owner": func.lower(Commitment.owner),
        "title": func.lower(Commitment.title),
        "progress": Commitment.progress,
    }
    column = columns[sort]
    query = query.order_by(
        column.desc() if direction == "desc" else column.asc(), Commitment.id
    )
    result = repo.page(query, page, page_size, clamp=True)
    result["members"] = [{"id": u.id, "name": u.name} for u in members]
    return result
