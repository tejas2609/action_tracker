from datetime import date
from app.services.dependency_graph import DependencyGraph


def assess(c, rows, edges, today=None):
    today = today or date.today()
    graph = edges if isinstance(edges, DependencyGraph) else DependencyGraph(edges)
    upstream = [rows[id] for id in graph.upstream.get(c.id, ()) if id in rows]
    pending = [x for x in upstream if x.status != "completed"]
    reasons = []
    if c.status in ("completed", "cancelled"):
        return {
            "level": "low",
            "reasons": [],
            "state": c.status,
            "next_action": "No follow-up required.",
        }
    if c.blocker:
        reasons.append(c.blocker)
    if c.condition and not c.condition_met:
        reasons.append("Waiting for condition: " + c.condition)
    reasons.extend("Waiting for " + x.owner + ": " + x.title for x in pending)
    days = (c.due_date - today).days if c.due_date else None
    blocked = bool(reasons)
    if days is not None and days < 0:
        reasons.append("Deadline passed " + str(-days) + " days ago")
    elif days is not None and days <= 3 and c.progress < 80:
        reasons.append("Due within three days with less than 80% progress")
    level = (
        "high"
        if (days is not None and days < 0)
        or (blocked and days is not None and days <= 3)
        else "medium" if reasons else "low"
    )
    state = (
        "waiting"
        if blocked
        else "overdue" if days is not None and days < 0 else "on-track"
    )
    return {
        "level": level,
        "reasons": reasons,
        "state": state,
        "next_action": (
            "Resolve upstream commitment with " + pending[0].owner
            if pending
            else (
                "Verify condition: " + c.condition
                if c.condition and not c.condition_met
                else (
                    "Discuss blocker: " + c.blocker
                    if c.blocker
                    else (
                        "Confirm a realistic completion date"
                        if level != "low"
                        else "Continue toward the agreed deadline"
                    )
                )
            )
        ),
        "overdue": days is not None and days < 0,
    }


def descendants(id, edges):
    graph = edges if isinstance(edges, DependencyGraph) else DependencyGraph(edges)
    return graph.descendants(id)


def serialize(c, rows, edges, include_impact=True):
    edges = edges if isinstance(edges, DependencyGraph) else DependencyGraph(edges)
    fields = [
        "id",
        "owner_id",
        "title",
        "owner",
        "due_date",
        "status",
        "progress",
        "condition",
        "condition_met",
        "blocker",
        "source_statement",
        "meeting_id",
    ]
    return {
        **{k: getattr(c, k) for k in fields},
        "risk": assess(c, rows, edges),
        "dependencies": list(edges.upstream.get(c.id, ())),
        "impact": list(descendants(c.id, edges)) if include_impact else [],
    }
