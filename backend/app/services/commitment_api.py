import re
from sqlalchemy import select
from fastapi import HTTPException
from datetime import date
from app.models.entities import Meeting, Commitment, Dependency
from app.models.people import User
from app.services.intelligence import serialize
from app.services.team_deadlines import team_missed_deadlines
from app.models.entities import Commitment, Dependency, Meeting
from app.services.intelligence import serialize
from app.models.entities import MeetingParticipant
from app.services.meeting_access_policy import require_workflow_access
from app.services.meeting_access_policy import readable_condition


def editable(s, id):
    c = s.s.get(Commitment, id)
    if c.owner_id != s.s.actor.id and s.s.actor.role != "Product Manager":
        raise HTTPException(
            403, "Only the owner or a Product Manager can edit this commitment."
        )
    return c


def health():
    return {"status": "ok", "version": "2.0.0"}


def commitments(scope="mine", q="", state="all", page=None, page_size=None, s=None):
    if scope not in ("mine", "organization"):
        raise HTTPException(422, "Invalid scope")
    snapshot = s.snapshot()
    rows = [
        c
        for c in s.listing(include_impact=False, snapshot=snapshot)
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
            or (c["risk"]["state"] == state)
            or (state == "overdue" and c["risk"].get("overdue"))
            or (
                state == "attention"
                and c["status"] == "active"
                and (c["risk"]["level"] != "low" or c["risk"].get("overdue"))
            )
        )
    ]
    items = rows[(page - 1) * page_size : page * page_size]
    for item in items:
        item["impact"] = list(snapshot[1].descendants(item["id"]))
    return {"items": items, "total": len(rows), "page": page, "page_size": page_size}


def team_deadlines(
    page=None,
    page_size=None,
    q="",
    owner_id="",
    due_from=None,
    due_to=None,
    blocked="all",
    sort="due_date",
    direction="asc",
    s=None,
):
    return team_missed_deadlines(
        s, page, page_size, q, owner_id, due_from, due_to, blocked, sort, direction
    )


def dashboard(missed_page=None, upcoming_page=None, page_size=None, s=None):

    mine = [c for c in s.listing() if c["owner_id"] == s.s.actor.id]
    active = [c for c in mine if c["status"] == "active"]
    today = date.today()
    missed = [c for c in active if c["due_date"] is not None and c["due_date"] < today]
    upcoming = [
        c for c in active if c["due_date"] is not None and c["due_date"] >= today
    ]
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
            "on_track": sum((c["risk"]["level"] == "low" for c in active)),
            "at_risk": sum((c["risk"]["level"] != "low" for c in active)),
            "blocked": sum((c["risk"]["state"] == "waiting" for c in active)),
            "overdue": len(missed),
            "completed": sum((c["status"] == "completed" for c in mine)),
        },
        "missed": paginate(missed, missed_page),
        "upcoming": paginate(upcoming, upcoming_page),
        "team_missed": (
            team_missed_deadlines(s, page_size=5) if s.s.actor.is_manager else None
        ),
    }


def graph(mode="immediate", s=None):
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


def meetings(s=None):
    return sorted(s.s.all(Meeting), key=lambda m: m.held_on, reverse=True)


def create_meeting(body, s=None):
    db = s.s.db
    actor = s.s.actor

    # The creator is always a participant.
    participant_ids = set(body.participant_ids)
    participant_ids.add(actor.id)

    valid_ids = set(
        db.scalars(
            select(User.id).where(
                User.id.in_(participant_ids),
                User.organization_id == actor.organization_id,
                User.active.is_(True),
            )
        )
    )

    if valid_ids != participant_ids:
        raise HTTPException(
            422,
            "Choose active participants from your organization.",
        )

    meeting = s.s.save(
        Meeting(
            title=body.title.strip(),
            held_on=body.held_on,
            transcript=body.transcript,
            visibility=body.visibility,
            organization_id=actor.organization_id,
        )
    )

    db.add_all(
        [
            MeetingParticipant(
                meeting_id=meeting.id,
                user_id=user_id,
            )
            for user_id in participant_ids
        ]
    )

    db.commit()
    return meeting


async def analyze(id, s=None):
    require_workflow_access(
        s.s.db,
        s.s.actor,
        id,
    )

    return await s.analyze(id)


def review(id, body, s=None):
    require_workflow_access(
        s.s.db,
        s.s.actor,
        id,
    )

    return s.review(id, body)


def detail(id, s=None):
    c = s.s.get(Commitment, id)
    rows, edges = s.snapshot()
    result = serialize(c, rows, edges)
    result["timeline"] = sorted(s.s.events_for(id), key=lambda e: e.created_at)
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


def update(id, body, s=None):
    editable(s, id)
    return s.update(id, body)


def edge(id, body, s=None):
    editable(s, id)
    s.edge(id, body.prerequisite_id)
    return {"ok": True}


def remove_edge(id, pre, s=None):
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


def replace_edge(id, pre, body, s=None):
    c = editable(s, id)
    s.s.get(Commitment, pre)
    s.s.get(Commitment, body.prerequisite_id)
    old = s.s.db.get(Dependency, (id, pre))
    if not old:
        raise HTTPException(404, "Dependency not found")
    if pre == body.prerequisite_id:
        return {"ok": True}
    s.s.db.delete(old)
    s.s.db.flush()
    s.s.event(
        c, "dependency_replaced", "Replaced " + pre + " with " + body.prerequisite_id
    )
    s.edge(id, body.prerequisite_id)
    return {"ok": True}


async def followup(id, body=None, s=None):
    recipient = None
    if body and body.recipient_id:
        u = s.s.db.get(User, body.recipient_id)
        if not u or not u.active or u.organization_id != s.s.actor.organization_id:
            raise HTTPException(404, "Recipient not found")
        recipient = {"id": u.id, "name": u.name}
    return await s.followup(id, recipient)


async def blocker_analysis(id, s=None):
    return await s.blocker_analysis(id)


async def search(body, s=None):
    return await s.search(body.query)


def create_manual_commitment(workflow, body):
    store = workflow.s
    actor = store.actor

    title = body.title.strip()
    if not title:
        raise HTTPException(422, "Enter a commitment title.")

    # Store.get enforces organization access.
    meeting = store.get(Meeting, body.meeting_id) if body.meeting_id else None

    # Validate every prerequisite before writing anything.
    prerequisite_ids = list(dict.fromkeys(body.prerequisite_ids))
    prerequisites = [
        store.get(Commitment, identifier) for identifier in prerequisite_ids
    ]

    commitment = store.save(
        Commitment(
            organization_id=actor.organization_id,
            owner_id=actor.id,
            owner=actor.name,
            title=title,
            source_statement=body.description.strip(),
            due_date=body.due_date,
            progress=body.progress,
            status="active",
            condition=body.condition.strip(),
            condition_met=body.condition_met,
            blocker=body.blocker.strip(),
            meeting_id=meeting.id if meeting else None,
        )
    )

    store.event(
        commitment,
        "created",
        "Created manually by " + actor.name,
        meeting_id=meeting.id if meeting else None,
    )

    for prerequisite in prerequisites:
        store.save(
            Dependency(
                commitment_id=commitment.id,
                prerequisite_id=prerequisite.id,
            )
        )
        store.event(
            commitment,
            "dependency_added",
            "Waiting for " + prerequisite.title,
        )

    # A new commitment with only existing prerequisites cannot create a cycle.
    # Commit the commitment, dependencies and events together.
    store.db.commit()

    rows, edges = workflow.snapshot()
    return serialize(commitment, rows, edges)


def meeting_options(store):
    rows = store.db.execute(
        select(
            Meeting.id,
            Meeting.title,
            Meeting.held_on,
            Meeting.transcript,
        )
        .where(readable_condition(store.actor))
        .order_by(Meeting.held_on.desc(), Meeting.id)
    )

    result = []
    for meeting in rows:
        speakers = set()

        for line in meeting.transcript.splitlines():
            match = re.match(r"^\s*([^:\n]{1,120}):\s+\S", line)
            if match:
                label = match.group(1).strip()
                if not label.isdigit():
                    speakers.add(label)

        result.append(
            {
                "id": meeting.id,
                "title": meeting.title,
                "held_on": meeting.held_on,
                "people": sorted(speakers, key=str.casefold),
            }
        )

    return result
