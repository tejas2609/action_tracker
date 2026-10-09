from sqlalchemy import select

from app.models.people import Message
from app.models.source_actions import SourceInbox


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

    db.add(
        SourceInbox(
            source="chat",
            external_id=message.id,
            organization_id=recipient.organization_id,
            recipient_id=recipient.id,
            payload={
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
                "timezone": "Asia/Kolkata",
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
    )
