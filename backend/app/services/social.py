import secrets, hashlib
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, or_, and_
from app.services.messaging import peer_user, conversation
from app.repositories.people import PeopleRepository
from app.core.config import settings
from app.models.people import User, LoginSession, Message
from app.models.entities import Commitment, Event
from app.services.chat_source import enqueue_chat


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
    if not settings.demo_login_enabled:
        raise HTTPException(403, "Development login is disabled.")
    username = body.username.strip().lower()
    if not username or not secrets.compare_digest(body.password, "pass"):
        raise HTTPException(401, "Invalid username or password.")
    matches = [
        user
        for user in PeopleRepository(db).active_users()
        if user.name.strip().lower() == username
    ]
    if len(matches) != 1:
        raise HTTPException(401, "Invalid username or password.")
    user = matches[0]
    if request is not None:
        request.state.user_id = user.id
        request.state.organization_id = user.organization_id
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
    )
    db.commit()
    return {"token": token, "user": public_user(user)}


def me(actor=None):
    return public_user(actor)


def logout(actor=None, db=None, credentials=None):

    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    PeopleRepository(db).revoke_session(token_hash)
    db.commit()
    return {"ok": True}


def users(q="", team="", role="", actor=None, db=None):
    rows = list(
        db.scalars(
            select(User)
            .where(User.organization_id == actor.organization_id, User.active == True)
            .order_by(User.name)
        )
    )
    filtered = [
        u
        for u in rows
        if (not q or q.casefold() in (u.name + " " + u.email).casefold())
        and (not team or u.team == team)
        and (not role or u.role == role)
    ]
    return {
        "items": [public_user(u) for u in filtered],
        "teams": sorted({u.team for u in rows}),
        "roles": sorted({u.role for u in rows}),
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
        if not c or c.organization_id != actor.organization_id or c.status == "review":
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
