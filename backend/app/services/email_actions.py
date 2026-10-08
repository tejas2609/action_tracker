from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.database import engine
from app.models.entities import Commitment, Event
from app.models.people import User
from app.models.integrations import GmailConnection
from app.models.email_actions import (
    CommitmentEmail,
    EmailOrigin,
    EmailProcessing,
    EmailSyncState,
)
from app.services.gmail_integration import now
from app.services.gmail_mailbox import GmailMailbox
from app.services.email_classifier import candidates, classify

BATCH_SIZE = 5


def owned_commitment(db, actor, commitment_id, review=False):
    commitment = db.scalar(
        select(Commitment)
        .where(
            Commitment.id == commitment_id,
            Commitment.owner_id == actor.id,
            Commitment.organization_id == actor.organization_id,
        )
        .with_for_update()
    )

    if not commitment or (review and commitment.status != "review"):
        raise HTTPException(404, "Commitment not found.")

    return commitment


def queue_messages(db, actor, google_sub, message_ids):
    for message_id in set(message_ids):
        db.execute(
            insert(EmailProcessing)
            .values(
                user_id=actor.id,
                google_sub=google_sub,
                message_id=message_id,
                state="queued",
            )
            .on_conflict_do_nothing()
        )


async def collect_page(db, actor, mailbox):
    state = db.get(EmailSyncState, actor.id)

    if state is None or state.google_sub != mailbox.google_sub:
        profile = await mailbox.profile()
        timestamp = now()

        if state is None:
            state = EmailSyncState(user_id=actor.id)
            db.add(state)

        state.google_sub = mailbox.google_sub
        state.history_id = profile["historyId"]
        state.history_page = None

        # Start with future messages. Do not fetch historical emails.
        state.bootstrap_done = True
        state.bootstrap_after = int(timestamp.timestamp())
        state.bootstrap_before = int(timestamp.timestamp())
        state.bootstrap_page = None

        state.last_history_sync = timestamp

        db.commit()
        return

    try:
        result = await mailbox.history(
            state.history_id,
            state.history_page,
        )

    except HTTPException as error:
        if error.status_code != 404:
            raise

        # History expired: establish a new baseline without backfilling.
        profile = await mailbox.profile()

        state.history_id = profile["historyId"]
        state.history_page = None
        state.bootstrap_done = True
        state.bootstrap_page = None
        state.last_history_sync = now()

        db.commit()
        return
    message_ids = []

    for history in result.get("history", []):
        for addition in history.get("messagesAdded", []):
            message_ids.append(addition["message"]["id"])

    queue_messages(
        db,
        actor,
        mailbox.google_sub,
        message_ids,
    )

    state.history_page = result.get("nextPageToken")

    if not state.history_page:
        state.history_id = result["historyId"]
        state.last_history_sync = now()

    db.commit()


def attach(db, actor, commitment, google_sub, email, description):
    existing = db.scalar(
        select(CommitmentEmail).where(
            CommitmentEmail.commitment_id == commitment.id,
            CommitmentEmail.user_id == actor.id,
            CommitmentEmail.google_sub == google_sub,
            CommitmentEmail.message_id == email["id"],
        )
    )

    if existing:
        return False

    db.add(
        CommitmentEmail(
            commitment_id=commitment.id,
            user_id=actor.id,
            google_sub=google_sub,
            message_id=email["id"],
            thread_id=email["thread_id"],
            subject=email["subject"],
            sender=email["sender"],
            received_at=email["received_at"],
            description=description,
            body_text=email["body_text"],
            truncated=email["truncated"],
        )
    )

    db.add(
        Event(
            commitment_id=commitment.id,
            kind="email_attached",
            message=description,
        )
    )

    return True


async def scan(db, actor, ai):
    # PostgreSQL session lock prevents overlapping scans across processes.
    with engine.connect() as lock_connection:
        key = "gmail-scan:" + actor.id

        locked = lock_connection.execute(
            text("SELECT pg_try_advisory_lock(" "hashtextextended(:key, 0))"),
            {"key": key},
        ).scalar_one()

        lock_connection.commit()

        if not locked:
            return {
                "busy": True,
                "processed": 0,
                "proposed": 0,
                "attached": 0,
            }

        try:
            return await scan_locked(db, actor, ai)

        finally:
            db.rollback()

            lock_connection.execute(
                text("SELECT pg_advisory_unlock(" "hashtextextended(:key, 0))"),
                {"key": key},
            )

            lock_connection.commit()


async def scan_locked(db, actor, ai):
    result = {
        "busy": False,
        "processed": 0,
        "proposed": 0,
        "attached": 0,
    }

    async with GmailMailbox(db, actor.id) as mailbox:
        await collect_page(db, actor, mailbox)

        queued = list(
            db.scalars(
                select(EmailProcessing)
                .where(
                    EmailProcessing.user_id == actor.id,
                    EmailProcessing.google_sub == mailbox.google_sub,
                    EmailProcessing.state == "queued",
                )
                .order_by(EmailProcessing.message_id)
                .limit(BATCH_SIZE)
            )
        )

        for queued_message in queued:
            try:
                email = await mailbox.message(queued_message.message_id)
                print(email)
            except HTTPException as error:
                if error.status_code != 404:
                    raise

                queued_message.state = "unavailable"
                db.commit()
                continue

            labels = set(email["labels"])

            if labels & {"SENT", "DRAFT", "SPAM", "TRASH"}:
                queued_message.state = "ignored"
                db.commit()
                continue

            if not email["body_text"]:
                queued_message.state = "ignored"
                db.commit()
                continue

            rows = candidates(db, actor, email)
            [
                print("Email matching candidates:", c.id, c.title, c.owner_id)
                for c in rows
            ]

            decision = await classify(
                ai,
                actor,
                mailbox.email,
                email,
                rows,
            )
            print(decision)
            # Re-check the connection after the AI request.
            connection = db.scalar(
                select(GmailConnection)
                .where(GmailConnection.user_id == actor.id)
                .execution_options(populate_existing=True)
                .with_for_update()
            )

            user = db.get(User, actor.id, populate_existing=True)

            if (
                not connection
                or connection.google_sub != mailbox.google_sub
                or not user
                or not user.active
            ):
                raise HTTPException(
                    409,
                    "Gmail connection or application user changed.",
                )

            allowed_ids = {commitment.id for commitment in rows}
            body = email["body_text"][:12000]

            linked_ids = set()

            for related in decision.related:
                if (
                    related.confidence < 0.90
                    or related.commitment_id not in allowed_ids
                    or related.commitment_id in linked_ids
                    or related.evidence not in body
                ):
                    continue

                commitment = db.scalar(
                    select(Commitment)
                    .where(
                        Commitment.id == related.commitment_id,
                        Commitment.owner_id == actor.id,
                        Commitment.organization_id == actor.organization_id,
                    )
                    .with_for_update()
                )

                if not commitment:
                    continue

                if attach(
                    db,
                    actor,
                    commitment,
                    mailbox.google_sub,
                    email,
                    related.description,
                ):
                    result["attached"] += 1

                linked_ids.add(commitment.id)

            proposed_titles = set()

            for task in decision.new_tasks:
                normalized = task.title.strip().casefold()

                if (
                    task.confidence < 0.85
                    or task.evidence not in body
                    or normalized in proposed_titles
                ):
                    continue

                commitment = Commitment(
                    id=str(uuid4()),
                    organization_id=actor.organization_id,
                    title=task.title.strip(),
                    owner=actor.name,
                    owner_id=actor.id,
                    due_date=task.due_date,
                    status="review",
                    progress=0,
                    condition="",
                    condition_met=False,
                    blocker="",
                    # Derived context, not a stored email body.
                    source_statement=task.description,
                    meeting_id=None,
                )

                db.add(commitment)
                db.flush()

                db.add(
                    EmailOrigin(
                        commitment_id=commitment.id,
                        user_id=actor.id,
                        google_sub=mailbox.google_sub,
                        message_id=email["id"],
                        thread_id=email["thread_id"],
                        subject=email["subject"],
                        sender=email["sender"],
                        received_at=email["received_at"],
                        description=task.description,
                    )
                )

                proposed_titles.add(normalized)
                result["proposed"] += 1

            queued_message.state = "processed"

            db.commit()

            result["processed"] += 1

    return result


def review_page(db, actor, page, page_size):
    filters = (
        Commitment.owner_id == actor.id,
        Commitment.organization_id == actor.organization_id,
        Commitment.status == "review",
    )

    total = db.scalar(select(func.count()).select_from(Commitment).where(*filters))

    rows = db.execute(
        select(Commitment, EmailOrigin)
        .join(
            EmailOrigin,
            EmailOrigin.commitment_id == Commitment.id,
        )
        .where(*filters)
        .order_by(EmailOrigin.received_at.desc(), Commitment.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": [
            {
                "id": commitment.id,
                "title": commitment.title,
                "due_date": commitment.due_date,
                "description": origin.description,
                "subject": origin.subject,
                "sender": origin.sender,
                "received_at": origin.received_at,
            }
            for commitment, origin in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def review_source(db, actor, commitment_id):
    owned_commitment(db, actor, commitment_id, review=True)

    origin = db.get(EmailOrigin, commitment_id)

    if not origin or origin.user_id != actor.id:
        raise HTTPException(404, "Email source not found.")

    # Release the commitment lock before contacting Google.
    db.commit()

    async with GmailMailbox(db, actor.id) as mailbox:
        if mailbox.google_sub != origin.google_sub:
            raise HTTPException(
                409,
                "Reconnect the Gmail account used by this proposal.",
            )

        return await mailbox.message(origin.message_id)


async def accept(db, actor, commitment_id, body):
    # Fetch the source before changing the proposal.
    email = await review_source(db, actor, commitment_id)

    commitment = owned_commitment(
        db,
        actor,
        commitment_id,
        review=True,
    )

    origin = db.get(EmailOrigin, commitment_id)

    connection = db.scalar(
        select(GmailConnection)
        .where(GmailConnection.user_id == actor.id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )

    if not connection or connection.google_sub != origin.google_sub:
        raise HTTPException(409, "Gmail connection changed.")

    commitment.title = body.title.strip()
    commitment.due_date = body.due_date
    commitment.status = "active"

    attach(
        db,
        actor,
        commitment,
        origin.google_sub,
        email,
        "Source email for the accepted commitment.",
    )

    db.add(
        Event(
            commitment_id=commitment.id,
            kind="email_proposal_accepted",
            message="User reviewed and accepted the email proposal.",
        )
    )

    db.commit()

    return {"id": commitment.id, "status": "active"}


def reject(db, actor, commitment_id):
    commitment = owned_commitment(
        db,
        actor,
        commitment_id,
        review=True,
    )

    # Remove related events if another email attached to this proposal.
    from sqlalchemy import delete

    db.execute(delete(Event).where(Event.commitment_id == commitment.id))

    db.delete(commitment)
    db.commit()

    return {"ok": True}


def attachment_page(db, actor, commitment_id, page, page_size):
    owned_commitment(db, actor, commitment_id)

    filters = (
        CommitmentEmail.commitment_id == commitment_id,
        CommitmentEmail.user_id == actor.id,
    )

    total = db.scalar(select(func.count()).select_from(CommitmentEmail).where(*filters))

    rows = list(
        db.scalars(
            select(CommitmentEmail)
            .where(*filters)
            .order_by(
                CommitmentEmail.received_at.desc(),
                CommitmentEmail.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    return {
        "items": [
            {
                "id": item.id,
                "subject": item.subject,
                "sender": item.sender,
                "received_at": item.received_at,
                "description": item.description,
                "body_text": item.body_text,
                "truncated": item.truncated,
            }
            for item in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def remove_attachment(db, actor, commitment_id, attachment_id):
    owned_commitment(db, actor, commitment_id)

    attachment = db.scalar(
        select(CommitmentEmail).where(
            CommitmentEmail.id == attachment_id,
            CommitmentEmail.commitment_id == commitment_id,
            CommitmentEmail.user_id == actor.id,
        )
    )

    if not attachment:
        raise HTTPException(404, "Email attachment not found.")

    db.delete(attachment)
    db.commit()

    return {"ok": True}
