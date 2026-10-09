"""Compatibility shim: extraction and retrieval are shared across sources."""

from app.services.sources.shared_classifier import (
    NewTask as NewTask,
    RelatedTask as RelatedTask,
    SOURCE_PROMPT as PROMPT,
    classify_payload,
)
from app.services.sources.source_candidates import find_candidates


def candidates(db, actor, email):
    return find_candidates(db, actor, email["subject"] + " " + email["body_text"])


def proposal_candidates(db, actor, tasks, existing_rows):
    rows = {row.id: row for row in existing_rows}
    for task in tasks:
        rows.update(
            {row.id: row for row in find_candidates(db, actor, task.title, limit=8)}
        )
    return list(rows.values())[:40]


async def classify(ai, actor, mailbox_email, email, rows):
    from app.services.sources.source_candidates import candidate_payload

    return await classify_payload(
        ai,
        PROMPT,
        {
            "recipient": {"id": actor.id, "name": actor.name, "email": mailbox_email},
            "source": "gmail",
            "timezone": actor.timezone,
            "current": {
                "body": email["body_text"],
                "subject": email["subject"],
                "sender": email["sender"],
                "sent_at": email["received_at"],
            },
            "preceding_context": [],
            "candidates": candidate_payload(rows),
        },
    )
