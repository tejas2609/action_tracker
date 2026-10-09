from sqlalchemy import select

from app.models.people import Message


def enqueue_chat(db, sender, recipient, message):
    previous = list(
        db.scalars(
            select(Message)
            .where(
                Message.conversation_id == message.conversation_id,
                Message.id != message.id,
            )
            .order_by(
                Message.created_at.desc(),
                Message.id.desc(),
            )
            .limit(8)
        )
    )

    previous.reverse()

    from app.services.sources.source_ingestion import SourceIngestionService

    SourceIngestionService(db).enqueue(
        "chat",
        message.id,
        recipient,
        {
            "commitment_id": message.commitment_id,
            "subject": "Chat message",
            "thread_id": message.conversation_id,
            "sender": {
                "id": sender.id,
                "name": sender.name,
                "email": sender.email,
            },
            "recipient": {
                "id": recipient.id,
                "name": recipient.name,
                "email": recipient.email,
            },
            "sent_at": message.created_at.isoformat(),
            "timezone": recipient.timezone,
            "body": message.body,
            "context": [
                {
                    "sender_id": item.sender_id,
                    "body": item.body[:1500],
                    "sent_at": item.created_at.isoformat(),
                }
                for item in previous
            ],
        },
    )
