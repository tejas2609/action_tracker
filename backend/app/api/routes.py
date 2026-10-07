from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date
from typing import Literal
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import current_user
from app.ai.provider import get_provider
from app.repositories.store import Store
from app.services.workflow import Workflow
from app.models.entities import Meeting, Commitment, Event, Dependency
from app.models.people import User
from app.schemas.contracts import (
    MeetingInput,
    Review,
    Update,
    EdgeInput,
    SearchInput,
    FollowupInput,
)
from app.services.intelligence import serialize
from app.services.team_deadlines import team_missed_deadlines

router = APIRouter(prefix="/api")


def service(
    db: Session = Depends(get_db),
    ai=Depends(get_provider),
    actor: User = Depends(current_user),
):
    return Workflow(Store(db, actor), ai)


def editable(s, id):
    c = s.s.get(Commitment, id)
    if c.owner_id != s.s.actor.id and s.s.actor.role != "Product Manager":
        raise HTTPException(
            403, "Only the owner or a Product Manager can edit this commitment."
        )
    return c


@router.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@router.get("/commitments")
def commitments(
    scope: str = "mine",
    q: str = "",
    state: str = "all",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    s=Depends(service),
):
    if scope not in ("mine", "organization"):
        raise HTTPException(422, "Invalid scope")
    rows = [
        c
        for c in s.listing()
        if scope == "organization" or c["owner_id"] == s.s.actor.id
    ]
    rows = [
        c
        for c in rows
        if q.casefold() in (c["title"] + " " + c["owner"]).casefold()
        and (
            state == "all"
            or c["status"] == state
            or c["risk"]["level"] == state
            or c["risk"]["state"] == state
            or state == "overdue"
            and c["risk"].get("overdue")
            or state == "attention"
            and c["status"] == "active"
            and (c["risk"]["level"] != "low" or c["risk"].get("overdue"))
        )
    ]
    return {
        "items": rows[(page - 1) * page_size : page * page_size],
        "total": len(rows),
        "page": page,
        "page_size": page_size,
    }


@router.get("/team-missed-deadlines")
def team_deadlines(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: str = "",
    owner_id: str = "",
    due_from: date | None = None,
    due_to: date | None = None,
    blocked: Literal["all", "yes", "no"] = "all",
    sort: Literal["due_date", "owner", "title", "progress"] = "due_date",
    direction: Literal["asc", "desc"] = "asc",
    s=Depends(service),
):
    return team_missed_deadlines(
        s,
        page,
        page_size,
        q,
        owner_id,
        due_from,
        due_to,
        blocked,
        sort,
        direction,
    )


@router.get("/dashboard")
def dashboard(
    missed_page: int = Query(1, ge=1),
    upcoming_page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=100),
    s=Depends(service),
):
    from datetime import date

    # Keep the dashboard scoped to the signed-in user's commitments.
    mine = [c for c in s.listing() if c["owner_id"] == s.s.actor.id]
    active = [c for c in mine if c["status"] == "active"]

    # Matches the date convention currently used by your risk engine.
    today = date.today()

    missed = [c for c in active if c["due_date"] is not None and c["due_date"] < today]

    upcoming = [
        c for c in active if c["due_date"] is not None and c["due_date"] >= today
    ]

    # Stable ordering: earliest deadline first.
    missed.sort(key=lambda c: (c["due_date"], c["id"]))
    upcoming.sort(key=lambda c: (c["due_date"], c["id"]))

    def paginate(rows, requested_page):
        total = len(rows)
        last_page = max(1, (total + page_size - 1) // page_size)
        actual_page = min(requested_page, last_page)
        start = (actual_page - 1) * page_size

        return {
            "items": rows[start : start + page_size],
            "total": total,
            "page": actual_page,
            "page_size": page_size,
        }

    return {
        "metrics": {
            "total": len(mine),
            "active": len(active),
            "on_track": sum(c["risk"]["level"] == "low" for c in active),
            "at_risk": sum(c["risk"]["level"] != "low" for c in active),
            "blocked": sum(c["risk"]["state"] == "waiting" for c in active),
            "overdue": len(missed),
            "completed": sum(c["status"] == "completed" for c in mine),
        },
        "missed": paginate(missed, missed_page),
        "upcoming": paginate(upcoming, upcoming_page),
        "team_missed": (
            team_missed_deadlines(s, page_size=5) if s.s.actor.is_manager else None
        ),
    }


@router.get("/graph")
def graph(mode: str = "immediate", s=Depends(service)):
    if mode not in ("immediate", "connected"):
        raise HTTPException(422, "Invalid graph mode")
    all = s.listing()
    mine = {c["id"] for c in all if c["owner_id"] == s.s.actor.id}
    ids = set(mine)
    edges = [(pre, c["id"]) for c in all for pre in c["dependencies"]]
    if mode == "immediate":
        for a, b in edges:
            if a in mine or b in mine:
                ids.update((a, b))
    else:
        pending = list(ids)
        adj = {}
        for a, b in edges:
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        while pending:
            for id in adj.get(pending.pop(), ()):
                if id not in ids:
                    ids.add(id)
                    pending.append(id)
    items = [{**c, "is_mine": c["id"] in mine} for c in all if c["id"] in ids]
    return {"items": items, "mine_ids": sorted(mine), "mode": mode}


@router.get("/meetings")
def meetings(s=Depends(service)):
    return sorted(s.s.all(Meeting), key=lambda m: m.held_on, reverse=True)


@router.post("/meetings", status_code=201)
def create_meeting(body: MeetingInput, s=Depends(service)):
    m = s.s.save(
        Meeting(**body.model_dump(), organization_id=s.s.actor.organization_id)
    )
    s.s.db.commit()
    return m


@router.post("/meetings/{id}/analyze")
async def analyze(id: str, s=Depends(service)):
    return await s.analyze(id)


@router.post("/meetings/{id}/review")
def review(id: str, body: Review, s=Depends(service)):
    return s.review(id, body)


@router.get("/commitments/{id}")
def detail(id: str, s=Depends(service)):
    c = s.s.get(Commitment, id)
    rows, edges = s.snapshot()
    result = serialize(c, rows, edges)
    result["timeline"] = sorted(
        [e for e in s.s.all(Event) if e.commitment_id == id], key=lambda e: e.created_at
    )
    result["meeting"] = s.s.get(Meeting, c.meeting_id) if c.meeting_id else None
    _, fingerprint = s.blocker_context(id)
    result["analysis"] = {
        "explanation": c.analysis_text,
        "next_action": c.analysis_next,
        "stale": c.analysis_hash != fingerprint,
        "revision": fingerprint,
    }
    ids = {id}
    pending = [id]
    while pending:
        n = pending.pop()
        for e in edges:
            if n in (e.commitment_id, e.prerequisite_id):
                other = e.prerequisite_id if n == e.commitment_id else e.commitment_id
                if other not in ids:
                    ids.add(other)
                    pending.append(other)
    result["related"] = [
        serialize(x, rows, edges) for x in rows.values() if x.id in ids
    ]
    result["can_edit"] = (
        c.owner_id == s.s.actor.id or s.s.actor.role == "Product Manager"
    )
    return result


@router.patch("/commitments/{id}")
def update(id: str, body: Update, s=Depends(service)):
    editable(s, id)
    return s.update(id, body)


@router.post("/commitments/{id}/dependencies", status_code=201)
def edge(id: str, body: EdgeInput, s=Depends(service)):
    editable(s, id)
    s.edge(id, body.prerequisite_id)
    return {"ok": True}


@router.delete("/commitments/{id}/dependencies/{pre}")
def remove_edge(id: str, pre: str, s=Depends(service)):
    c = editable(s, id)
    s.s.get(Commitment, pre)
    e = s.s.db.get(Dependency, (id, pre))
    if e:
        before = s.risk_levels()
        s.s.db.delete(e)
        s.s.db.flush()
        s.s.event(c, "dependency_removed", "Removed prerequisite " + pre)
        s.audit_risks(before)
        s.s.db.commit()
    return {"ok": True}


@router.post("/commitments/{id}/dependencies/{pre}/replace")
def replace_edge(id: str, pre: str, body: EdgeInput, s=Depends(service)):
    c = editable(s, id)
    s.s.get(Commitment, pre)
    s.s.get(Commitment, body.prerequisite_id)
    old = s.s.db.get(Dependency, (id, pre))
    if not old:
        raise HTTPException(404, "Dependency not found")
    if pre == body.prerequisite_id:
        return {"ok": True}
    before = s.risk_levels()
    s.s.db.delete(old)
    s.s.db.flush()
    # edge commits both changes transactionally; get_db rolls back if cycle check fails.
    s.s.event(
        c, "dependency_replaced", "Replaced " + pre + " with " + body.prerequisite_id
    )
    s.edge(id, body.prerequisite_id)
    return {"ok": True}


@router.post("/commitments/{id}/followup")
async def followup(id: str, body: FollowupInput | None = None, s=Depends(service)):
    recipient = None
    if body and body.recipient_id:
        u = s.s.db.get(User, body.recipient_id)
        if not u or not u.active or u.organization_id != s.s.actor.organization_id:
            raise HTTPException(404, "Recipient not found")
        recipient = {"id": u.id, "name": u.name}
    return await s.followup(id, recipient)


@router.post("/commitments/{id}/analysis")
async def blocker_analysis(id: str, s=Depends(service)):
    return await s.blocker_analysis(id)


@router.post("/search")
async def search(body: SearchInput, s=Depends(service)):
    return await s.search(body.query)
