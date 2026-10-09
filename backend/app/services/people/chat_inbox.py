from fastapi import HTTPException
from sqlalchemy import select, func, and_, or_, case, update

from app.models.people import User, Conversation, Message
from app.services.people.messaging import peer_user, conversation
from app.services.people.social import public_user


def inbox(db, actor, page=1, page_size=100):
    peer_scope = (
        User.organization_id == actor.organization_id,
        User.active.is_(True),
        User.id != actor.id,
    )

    conversation_match = and_(
        Conversation.organization_id == actor.organization_id,
        or_(
            and_(
                Conversation.user_a_id == actor.id,
                Conversation.user_b_id == User.id,
            ),
            and_(
                Conversation.user_b_id == actor.id,
                Conversation.user_a_id == User.id,
            ),
        ),
    )

    # Indexed lookup of the most recent message, without loading its body.
    latest_at = (
        select(Message.created_at)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )

    unread = (
        select(func.count(Message.id))
        .where(
            Message.conversation_id == Conversation.id,
            Message.sender_id == User.id,
            Message.read_at.is_(None),
        )
        .correlate(Conversation, User)
        .scalar_subquery()
    )

    query = (
        select(
            User,
            Conversation.id.label("conversation_id"),
            latest_at.label("last_message_at"),
            unread.label("unread_count"),
        )
        .outerjoin(Conversation, conversation_match)
        .where(*peer_scope)
        .order_by(
            # Unread conversations first, newest activity within each group.
            case((unread > 0, 0), else_=1),
            latest_at.desc().nullslast(),
            User.name,
            User.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    total = db.scalar(select(func.count(User.id)).where(*peer_scope))

    return {
        "items": [
            {
                **public_user(user),
                "conversation_id": conversation_id,
                "last_message_at": last_message_at,
                "unread_count": int(unread_count or 0),
            }
            for user, conversation_id, last_message_at, unread_count in db.execute(
                query
            )
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def mark_read(db, actor, peer_id, through_id):
    peer = peer_user(db, actor, peer_id)
    conv = conversation(db, actor, peer)

    through = db.scalar(
        select(Message).where(
            Message.id == through_id,
            Message.conversation_id == conv.id,
        )
    )

    if through is None:
        raise HTTPException(422, "Invalid read cursor")

    # Only mark messages through the last message displayed.
    # A newer message arriving during this request remains unread.
    db.execute(
        update(Message)
        .where(
            Message.conversation_id == conv.id,
            Message.sender_id == peer.id,
            Message.read_at.is_(None),
            or_(
                Message.created_at < through.created_at,
                and_(
                    Message.created_at == through.created_at,
                    Message.id <= through.id,
                ),
            ),
        )
        .values(read_at=func.now())
        .execution_options(synchronize_session=False)
    )

    db.commit()
    return {"ok": True}
