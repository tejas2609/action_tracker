"""Explicit whole-component deletion with a reviewable impact preview."""

from sqlalchemy import select, delete, or_
from fastapi import HTTPException
from app.models.entities import Meeting, Commitment, Dependency, Event


def deletion_plan(db, meeting_id):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Meeting not found")
    query = select(Commitment)
    if meeting.organization_id:
        query = query.where(
            Commitment.organization_id == meeting.organization_id,
            Commitment.status != "review",
        )
    commitments = list(db.scalars(query))
    edges = list(db.scalars(select(Dependency)))
    mentioned = set(
        db.scalars(select(Event.commitment_id).where(Event.meeting_id == meeting_id))
    )
    seeds = {
        c.id for c in commitments if c.meeting_id == meeting_id or c.id in mentioned
    }
    adjacency = {c.id: set() for c in commitments}
    eligible = set(adjacency)
    for edge in edges:
        if edge.commitment_id not in eligible or edge.prerequisite_id not in eligible:
            continue
        adjacency.setdefault(edge.commitment_id, set()).add(edge.prerequisite_id)
        adjacency.setdefault(edge.prerequisite_id, set()).add(edge.commitment_id)
    affected = set(seeds)
    pending = list(seeds)
    while pending:
        for linked in adjacency.get(pending.pop(), ()):
            if linked not in affected:
                affected.add(linked)
                pending.append(linked)
    records = [c for c in commitments if c.id in affected]
    events = list(
        db.scalars(
            select(Event).where(
                or_(Event.commitment_id.in_(affected), Event.meeting_id == meeting_id)
            )
        )
    )
    other_ids = {c.meeting_id for c in records if c.meeting_id != meeting_id}
    other_ids.update(
        e.meeting_id for e in events if e.meeting_id and e.meeting_id != meeting_id
    )
    meetings = list(db.scalars(select(Meeting).where(Meeting.id.in_(other_ids))))
    return {
        "meeting_id": meeting_id,
        "meeting_title": meeting.title,
        "commitment_ids": sorted(affected),
        "commitments": [
            dict(
                id=c.id,
                title=c.title,
                owner=c.owner,
                meeting_id=c.meeting_id,
                direct=c.id in seeds,
            )
            for c in sorted(records, key=lambda c: (c.owner, c.title, c.id))
        ],
        "commitment_count": len(affected),
        "dependency_count": sum(
            e.commitment_id in affected or e.prerequisite_id in affected for e in edges
        ),
        "event_count": len(events),
        "other_meetings": [
            dict(id=m.id, title=m.title)
            for m in sorted(meetings, key=lambda m: m.title)
        ],
    }


def delete_meeting(db, meeting_id, expected_ids):
    plan = deletion_plan(db, meeting_id)
    ids = set(plan["commitment_ids"])
    if ids != set(expected_ids):
        raise HTTPException(
            409, "Linked commitments changed. Preview deletion again before confirming."
        )
    # Remove referencing rows first to respect foreign keys.
    db.execute(
        delete(Dependency).where(
            or_(Dependency.commitment_id.in_(ids), Dependency.prerequisite_id.in_(ids))
        )
    )
    db.execute(
        delete(Event).where(
            or_(Event.commitment_id.in_(ids), Event.meeting_id == meeting_id)
        )
    )
    db.execute(delete(Commitment).where(Commitment.id.in_(ids)))
    # Remove stale AI suggestions referencing deleted commitment IDs.
    for meeting in db.scalars(select(Meeting).where(Meeting.id != meeting_id)):
        changed = False
        updated = []
        for finding in meeting.findings or []:
            item = dict(finding)
            if item.get("existing_id") in ids:
                item["existing_id"] = None
                changed = True
            prerequisites = item.get("prerequisite_ids", [])
            kept = [id for id in prerequisites if id not in ids]
            if kept != prerequisites:
                item["prerequisite_ids"] = kept
                changed = True
            updated.append(item)
        if changed:
            meeting.findings = updated
    db.execute(delete(Meeting).where(Meeting.id == meeting_id))
    db.commit()
    return {
        "deleted_meeting_id": meeting_id,
        "deleted_commitment_count": len(ids),
        "deleted_dependency_count": plan["dependency_count"],
        "deleted_event_count": plan["event_count"],
    }
