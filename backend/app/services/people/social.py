import hashlib
from fastapi import HTTPException
from sqlalchemy import select, or_, and_
from app.services.people.messaging import peer_user, conversation
from app.repositories.people import PeopleRepository
from app.models.people import User, Message
from app.models.entities import Commitment, Event
from app.services.sources.chat_source import enqueue_chat
from app.services.notifications.notifications import notify


def public_user(u):
    return {
        key: getattr(u, key)
        for key in (
            "id",
            "organization_id",
            "name",
            "email",
            "team",
            "role",
            "active",
            "is_manager",
            "manager_id",
        )
    }


def capabilities(actor=None):
    return {
        "text_messages": True,
        "attachments": False,
        "transport": "polling",
        "poll_interval_ms": 3000,
        "max_message_characters": 10000,
    }


def password_login(body, db=None, request=None):
    from app.services.people.authentication import AuthenticationService

    return AuthenticationService(db).login(body, request)


def me(actor=None):
    return public_user(actor)


def logout(actor=None, db=None, credentials=None):

    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    PeopleRepository(db).revoke_session(token_hash)
    db.commit()
    return {"ok": True}


def users(q="", team="", role="", actor=None, db=None, page=1, page_size=100):
    from sqlalchemy import func

    query = select(User).where(
        User.organization_id == actor.organization_id, User.active.is_(True)
    )
    if q:
        query = query.where(
            or_(
                func.lower(User.name).contains(q.casefold(), autoescape=True),
                func.lower(User.email).contains(q.casefold(), autoescape=True),
            )
        )
    if team:
        query = query.where(User.team == team)
    if role:
        query = query.where(User.role == role)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = list(
        db.scalars(
            query.order_by(User.name, User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    facets = (
        select(User.team, User.role)
        .where(User.organization_id == actor.organization_id, User.active.is_(True))
        .distinct()
    )
    values = list(db.execute(facets))
    return {
        "items": [public_user(u) for u in rows],
        "teams": sorted({v.team for v in values}),
        "roles": sorted({v.role for v in values}),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_chat(peer_id, before=None, limit=None, actor=None, db=None):
    peer = peer_user(db, actor, peer_id)
    c = conversation(db, actor, peer)
    q = select(Message).where(Message.conversation_id == c.id)
    if before:
        cursor = db.get(Message, before)
        if not cursor or cursor.conversation_id != c.id:
            raise HTTPException(422, "Invalid message cursor")
        q = q.where(
            or_(
                Message.created_at < cursor.created_at,
                and_(Message.created_at == cursor.created_at, Message.id < cursor.id),
            )
        )
    messages = list(
        db.scalars(
            q.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
        )
    )
    has_more = len(messages) > limit
    messages = messages[:limit]
    messages.reverse()
    db.commit()
    return {
        "conversation_id": c.id,
        "peer": public_user(peer),
        "items": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "body": m.body,
                "commitment_id": m.commitment_id,
                "created_at": m.created_at,
                "attachments": [],
            }
            for m in messages
        ],
        "has_more": has_more,
        "before": messages[0].id if messages else None,
    }


def send(peer_id, body, actor=None, db=None):
    peer = peer_user(db, actor, peer_id)
    if not body.body.strip():
        raise HTTPException(422, "Message cannot be blank")
    if body.commitment_id:
        c = db.get(Commitment, body.commitment_id)
        from app.core.permissions import can_read

        if not can_read(actor, c) or c.status == "review":
            raise HTTPException(404, "Commitment not found")
    conv = conversation(db, actor, peer)
    msg = Message(
        conversation_id=conv.id,
        sender_id=actor.id,
        body=body.body.strip(),
        commitment_id=body.commitment_id,
    )
    db.add(msg)
    db.flush()
    enqueue_chat(db, actor, peer, msg)
    notify(
        db,
        organization_id=actor.organization_id,
        recipient_id=peer.id,
        kind="chat",
        title=f"New message from {actor.name}",
        event_key=f"chat:{msg.id}",
        peer_id=actor.id,
    )
    if body.commitment_id:
        db.add(
            Event(
                commitment_id=body.commitment_id,
                kind="followup_sent",
                message=actor.name + " sent a chat follow-up to " + peer.name,
            )
        )
    db.commit()
    return {
        "id": msg.id,
        "conversation_id": conv.id,
        "sender_id": msg.sender_id,
        "body": msg.body,
        "commitment_id": msg.commitment_id,
        "created_at": msg.created_at,
        "attachments": [],
    }


def attachments(peer_id, actor=None, db=None):
    peer_user(db, actor, peer_id)
    raise HTTPException(
        501, "Attachments are planned for a later version. Upload is disabled."
    )
