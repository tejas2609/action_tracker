import asyncio
from datetime import timedelta

from sqlalchemy import func, select, text

from app.models.entities import Commitment, Event, now
from app.models.people import User
from app.models.source_actions import CommitmentSource, SourceInbox
from app.services.shared_classifier import (
    SOURCE_PROMPT,
    classify_payload,
    evidence_in_body,
)
from app.services.source_candidates import (
    candidate_payload,
    find_candidates,
)


def attach(db, job, commitment, kind, item):
    existing = db.scalar(
        select(CommitmentSource.id).where(
            CommitmentSource.inbox_id == job.id,
            CommitmentSource.commitment_id == commitment.id,
        )
    )

    if existing:
        return

    db.add(
        CommitmentSource(
            inbox_id=job.id,
            commitment_id=commitment.id,
            kind=kind,
            description=item.description,
            evidence=item.evidence,
        )
    )

    db.add(
        Event(
            commitment_id=commitment.id,
            kind="source_attached",
            message=f"{job.source}: {item.description}",
        )
    )


async def process_job(db, job, ai):
    actor = db.get(User, job.recipient_id)

    if not actor or not actor.active or actor.organization_id != job.organization_id:
        job.state = "ignored"
        return

    payload = job.payload
    body = payload["body"][:12000]

    thread_ids = list(
        db.scalars(
            select(CommitmentSource.commitment_id)
            .join(
                SourceInbox,
                SourceInbox.id == CommitmentSource.inbox_id,
            )
            .where(
                SourceInbox.recipient_id == actor.id,
                SourceInbox.organization_id == actor.organization_id,
                SourceInbox.source == job.source,
                SourceInbox.payload["thread_id"].as_string()
                == payload.get("thread_id", ""),
            )
            .order_by(CommitmentSource.created_at.desc())
            .limit(10)
        )
    )

    context_text = " ".join(message["body"] for message in payload.get("context", []))
    print(context_text)
    rows = find_candidates(
        db,
        actor,
        body + " " + context_text,
        thread_ids,
    )
    print(rows)

    async def decide(candidates):
        current = {key: value for key, value in payload.items() if key != "context"}
        current["body"] = body

        return await classify_payload(
            ai,
            SOURCE_PROMPT,
            {
                "recipient": {
                    "id": actor.id,
                    "name": actor.name,
                    "email": actor.email,
                },
                "source": job.source,
                "timezone": payload.get("timezone", "UTC"),
                "current": current,
                "preceding_context": payload.get("context", []),
                "candidates": candidate_payload(candidates),
            },
        )

    decision = await decide(rows)
    print(decision)
    # Search each proposed deliverable before creating new work.
    expanded = {commitment.id: commitment for commitment in rows}

    for task in decision.new_tasks:
        for commitment in find_candidates(
            db,
            actor,
            task.title,
            limit=8,
        ):
            expanded[commitment.id] = commitment

    if set(expanded) != {commitment.id for commitment in rows}:
        rows = list(expanded.values())
        decision = await decide(rows)

    allowed_ids = {commitment.id for commitment in rows}
    linked_ids = set()

    for item in decision.related:
        if (
            item.confidence < 0.90
            or item.commitment_id not in allowed_ids
            or item.commitment_id in linked_ids
            or not evidence_in_body(item.evidence, body)
        ):
            continue

        commitment = db.scalar(
            select(Commitment)
            .where(
                Commitment.id == item.commitment_id,
                Commitment.owner_id == actor.id,
                Commitment.organization_id == actor.organization_id,
            )
            .with_for_update()
        )

        if commitment:
            attach(db, job, commitment, "related", item)
            linked_ids.add(commitment.id)

    seen_titles = set()

    for item in decision.new_tasks:
        title = item.title.strip()
        normalized_title = title.casefold()

        if (
            item.confidence < 0.85
            or normalized_title in seen_titles
            or not evidence_in_body(item.evidence, body)
        ):
            continue

        seen_titles.add(normalized_title)

        existing = list(
            db.scalars(
                select(Commitment)
                .where(
                    Commitment.owner_id == actor.id,
                    Commitment.organization_id == actor.organization_id,
                    Commitment.status.in_(["active", "review"]),
                    func.lower(func.trim(Commitment.title)) == title.lower(),
                )
                .with_for_update()
            )
        )

        # Conservative fallback for identical open-task titles.
        if existing:
            if len(existing) == 1 and existing[0].id not in linked_ids:
                attach(db, job, existing[0], "related", item)
                linked_ids.add(existing[0].id)

            continue

        commitment = Commitment(
            title=title,
            owner=actor.name,
            owner_id=actor.id,
            organization_id=actor.organization_id,
            status="review",
            progress=0,
            due_date=item.due_date,
            source_statement=item.description,
            meeting_id=None,
            condition="",
            condition_met=False,
            blocker="",
        )

        db.add(commitment)
        db.flush()

        attach(db, job, commitment, "proposal", item)

    job.state = "processed"


async def process_next(db, ai):
    job = db.scalar(
        select(SourceInbox)
        .where(
            SourceInbox.state == "queued",
            SourceInbox.available_at <= now(),
        )
        .order_by(SourceInbox.created_at, SourceInbox.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if not job:
        db.rollback()
        return False

    # Prevent concurrent generic-source extraction for one recipient.
    locked = db.scalar(
        text("SELECT pg_try_advisory_xact_lock(" "hashtextextended(:key, 0))"),
        {"key": "commitment-source:" + job.recipient_id},
    )

    if not locked:
        db.rollback()
        return False

    try:
        # Roll back partial proposals/associations if processing fails.
        with db.begin_nested():
            await asyncio.wait_for(
                process_job(db, job, ai),
                timeout=60,
            )
            db.flush()

        job.last_error = ""

    except Exception as error:
        job.attempts += 1
        job.last_error = type(error).__name__[:120]

        job.state = "failed" if job.attempts >= 5 else "queued"

        job.available_at = now() + timedelta(
            seconds=min(300, 15 * 2**job.attempts),
        )

    db.commit()
    return True
