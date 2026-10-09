import asyncio
from datetime import timedelta

from sqlalchemy import func, select, text

from app.models.entities import Commitment, Event, now
from app.models.people import User
from app.models.source_actions import CommitmentSource, SourceInbox
from app.services.sources.shared_classifier import (
    SOURCE_PROMPT,
    classify_payload,
    evidence_in_body,
)
from app.services.sources.source_candidates import (
    candidate_payload,
    find_candidates,
)


def attach(db, job, commitment, kind, item):

    current = db.scalar(
        select(Commitment)
        .where(
            Commitment.id == commitment.id,
            Commitment.organization_id == job.organization_id,
            Commitment.owner_id == job.recipient_id,
            Commitment.status.in_(["active", "review", "completed"]),
        )
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if current is None:
        return

    commitment = current

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
            proposed_changes=(
                item.proposed_changes.model_dump(mode="json", exclude_unset=True)
                if hasattr(item, "proposed_changes")
                else {}
            ),
            description=item.description,
            evidence=item.evidence,
        )
    )

    if job.source == "gmail":
        from app.models.email_actions import CommitmentEmail, EmailOrigin

        payload = job.payload
        from datetime import datetime

        received = datetime.fromisoformat(payload["sent_at"])
        db.add(
            CommitmentEmail(
                commitment_id=commitment.id,
                user_id=job.recipient_id,
                google_sub=payload["google_sub"],
                message_id=job.external_id,
                thread_id=job.thread_id,
                subject=payload["subject"],
                sender=payload["sender"]["email"],
                received_at=received,
                body_text=payload["body"],
                truncated=False,
                description=item.description,
            )
        )
        if kind == "proposal":
            db.add(
                EmailOrigin(
                    commitment_id=commitment.id,
                    user_id=job.recipient_id,
                    google_sub=payload["google_sub"],
                    message_id=job.external_id,
                    thread_id=job.thread_id,
                    subject=payload["subject"],
                    sender=payload["sender"]["email"],
                    received_at=received,
                    description=item.description,
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

    from app.schemas.sources import SourceMessage

    payload = SourceMessage.model_validate(job.payload).model_dump(mode="json")
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
                SourceInbox.thread_id == payload.get("thread_id", ""),
            )
            .order_by(CommitmentSource.created_at.desc())
            .limit(10)
        )
    )

    if payload.get("commitment_id"):
        thread_ids.insert(0, payload["commitment_id"])

    context_text = " ".join(message["body"] for message in payload.get("context", []))
    rows = find_candidates(
        db,
        actor,
        body + " " + context_text,
        thread_ids,
    )

    async def decide(candidates, proposed_tasks=None):
        current = {key: value for key, value in payload.items() if key != "context"}
        current["body"] = body

        classification_input = {
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
        }

        prompt = SOURCE_PROMPT

        if proposed_tasks:
            classification_input["unverified_proposals"] = [
                task.model_dump(mode="json") for task in proposed_tasks
            ]

            prompt += """
Additional verification:
The unverified_proposals are an earlier model's suggestions, not facts.
Recheck the CURRENT message independently against the supplied candidates.

For each suggested new task, determine whether it is:
1. A change to an existing deliverable's scope or contents: return related.
2. An independently requested deliverable: retain it in new_tasks.
3. Unsupported or ambiguous: omit it.

Compare actions, deliverables, named people, and sender/recipient direction.
A different proposed title does not establish a different deliverable.
Do not force a relationship merely because candidates exist.
Return the complete final decision, including any supported related updates.
"""

        return await classify_payload(
            ai,
            prompt,
            classification_input,
        )

    decision = await decide(rows)

    if decision.new_tasks:
        # Search using each proposed deliverable as well as the message.
        # Preserve the initial candidates, including thread-linked tasks.
        expanded = {commitment.id: commitment for commitment in rows}

        for task in decision.new_tasks:
            query_text = f"{task.title} {task.description}"

            for commitment in find_candidates(
                db,
                actor,
                query_text,
                limit=8,
            ):
                expanded.setdefault(commitment.id, commitment)

        rows = list(expanded.values())[:40]

        # Previously, this check ran only when new candidate IDs appeared.
        # It now also checks scope changes against candidates already found.
        if rows:
            decision = await decide(
                rows,
                proposed_tasks=decision.new_tasks,
            )

    from app.core.concurrency import lock_organization

    lock_organization(db, actor.organization_id)
    db.expire_all()
    actor = db.get(User, job.recipient_id, populate_existing=True)
    if not actor or not actor.active or actor.organization_id != job.organization_id:
        job.state = "ignored"
        return
    if job.state != "processing" or job.claimed_until is None:
        raise RuntimeError("Job claim lost")
    expiry = job.claimed_until
    if expiry.tzinfo is None:
        from datetime import timezone

        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now():
        raise RuntimeError("Job claim expired")
    if job.source == "gmail":
        from app.models.integrations import GmailConnection

        connection = db.get(GmailConnection, actor.id, populate_existing=True)
        if not connection or connection.google_sub != payload.get("google_sub"):
            job.state = "ignored"
            return
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
                Commitment.status.in_(["active", "review", "completed"]),
            )
            .execution_options(populate_existing=True)
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


def claim_next(db):
    """Short transaction: claim one ready recipient, skip busy recipients."""
    from sqlalchemy import or_, and_
    from sqlalchemy.orm import aliased
    from app.models.entities import uid

    other = aliased(SourceInbox)
    busy = (
        select(other.id)
        .where(
            other.recipient_id == SourceInbox.recipient_id,
            other.state == "processing",
            other.claimed_until > now(),
        )
        .exists()
    )
    ready = or_(
        and_(SourceInbox.state == "queued", SourceInbox.available_at <= now()),
        and_(SourceInbox.state == "processing", SourceInbox.claimed_until <= now()),
    )
    jobs = list(
        db.scalars(
            select(SourceInbox)
            .where(ready, ~busy)
            .order_by(SourceInbox.created_at, SourceInbox.id)
            .with_for_update(skip_locked=True)
            .limit(20)
        )
    )
    for job in jobs:
        if db.bind.dialect.name == "postgresql":
            locked = db.scalar(
                text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": "commitment-source:" + job.recipient_id},
            )
            if not locked:
                continue
            # Recheck after obtaining recipient mutex under READ COMMITTED.
            if db.scalar(
                select(SourceInbox.id)
                .where(
                    SourceInbox.recipient_id == job.recipient_id,
                    SourceInbox.state == "processing",
                    SourceInbox.claimed_until > now(),
                )
                .limit(1)
            ):
                continue
        from app.core.config import settings

        job.state = "processing"
        job.claim_token = uid()
        job.claimed_until = now() + timedelta(seconds=settings.worker_lease_seconds)
        claim = (job.id, job.claim_token)
        db.commit()
        return claim
    db.rollback()
    return None


async def execute_claim(session_factory, claim, ai):
    """Thread-confined session; read transaction released before each AI call."""
    from app.ai.session_provider import SessionAwareProvider

    job_id, token = claim
    with session_factory() as db:
        job = db.get(SourceInbox, job_id)
        if not job or job.claim_token != token:
            return
        try:
            await asyncio.wait_for(
                process_job(db, job, SessionAwareProvider(ai, db)), timeout=240
            )
            if job.claim_token != token:
                raise RuntimeError("Job claim lost")
            job.last_error = ""
            job.claim_token = None
            job.claimed_until = None
            db.commit()
        except Exception as error:
            db.rollback()
            job = db.scalar(
                select(SourceInbox)
                .where(SourceInbox.id == job_id, SourceInbox.claim_token == token)
                .with_for_update()
            )
            if job:
                job.attempts += 1
                job.last_error = type(error).__name__[:120]
                job.state = "failed" if job.attempts >= 5 else "queued"
                job.available_at = now() + timedelta(
                    seconds=min(300, 15 * 2**job.attempts)
                )
                job.claim_token = None
                job.claimed_until = None
                db.commit()


async def process_next(db, ai):
    # Backward-compatible entry point; worker uses explicit session factory.
    from sqlalchemy.orm import sessionmaker

    claim = claim_next(db)
    if not claim:
        return False
    await execute_claim(sessionmaker(db.bind, expire_on_commit=False), claim, ai)
    return True
