from typing import Protocol
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.source_actions import SourceInbox
from app.schemas.sources import SourceMessage


class SourceAdapter(Protocol):
    def normalize(self, raw: dict) -> SourceMessage: ...


class SourceIngestionService:
    def __init__(self, db):
        self.db = db

    def enqueue(self, source, external_id, actor, payload):
        message = SourceMessage.model_validate(payload)
        if message.recipient.id != actor.id:
            raise ValueError("Recipient mismatch")
        if not 1 <= len(source) <= 40 or not 1 <= len(external_id) <= 255:
            raise ValueError("Invalid source identifier")
        filters = (
            SourceInbox.source == source,
            SourceInbox.external_id == external_id,
            SourceInbox.recipient_id == actor.id,
        )
        existing = self.db.scalar(select(SourceInbox).where(*filters))
        if existing:
            return existing
        try:
            with self.db.begin_nested():
                job = SourceInbox(
                    source=source,
                    external_id=external_id,
                    organization_id=actor.organization_id,
                    recipient_id=actor.id,
                    thread_id=message.thread_id,
                    payload=message.model_dump(mode="json"),
                )
                self.db.add(job)
                self.db.flush()
                return job
        except IntegrityError:
            return self.db.scalar(select(SourceInbox).where(*filters))
