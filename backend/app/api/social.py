import secrets, hashlib
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session
from app.services.messaging import peer_user, conversation
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.auth import current_user, security
from fastapi.security import HTTPAuthorizationCredentials
from app.core.config import settings
from app.models.people import User, LoginSession, Conversation, Message
from app.models.entities import Commitment, Meeting, Event

router = APIRouter(prefix="/api", tags=["Users and chat"])


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


class AttachmentMetadata(BaseModel):
    id: str
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=0)
    uploaded_by: str
    created_at: datetime


class Login(BaseModel):
    user_id: str


class PasswordLogin(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class MessageInput(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    commitment_id: str | None = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=0)


@router.get("/messaging/capabilities")
def capabilities(actor: User = Depends(current_user)):
    return {
        "text_messages": True,
        "attachments": False,
        "transport": "polling",
        "poll_interval_ms": 3000,
        "max_message_characters": 10000,
    }


@router.post("/auth/login")
def password_login(
    body: PasswordLogin,
    db: Session = Depends(get_db),
):
    # Use your existing development-login configuration.
    if not settings.demo_login_enabled:
        raise HTTPException(403, "Development login is disabled.")

    username = body.username.strip().lower()

    if not username or not secrets.compare_digest(body.password, "pass"):
        raise HTTPException(401, "Invalid username or password.")

    # Names are not unique in the current database.
    # Reject ambiguous matches rather than choosing someone silently.
    matches = [
        user
        for user in db.scalars(select(User).where(User.active == True))
        if user.name.strip().lower() == username
    ]

    if len(matches) != 1:
        raise HTTPException(401, "Invalid username or password.")

    user = matches[0]
    token = secrets.token_urlsafe(32)

    db.add(
        LoginSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
    )
    db.commit()

    return {
        "token": token,
        "user": public_user(user),
    }


@router.get("/auth/me")
def me(actor: User = Depends(current_user)):
    return public_user(actor)


@router.post("/auth/logout")
def logout(
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    # Revoke only this browser session; other users/windows keep their sessions.
    from sqlalchemy import delete

    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash))
    db.commit()
    return {"ok": True}


@router.get("/users")
def users(
    q: str = "",
    team: str = "",
    role: str = "",
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
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


@router.get("/chat/{peer_id}")
def get_chat(
    peer_id: str,
    before: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
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


@router.post("/chat/{peer_id}", status_code=201)
def send(
    peer_id: str,
    body: MessageInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    peer = peer_user(db, actor, peer_id)
    if not body.body.strip():
        raise HTTPException(422, "Message cannot be blank")
    if body.commitment_id:
        c = db.get(Commitment, body.commitment_id)
        meeting = db.get(Meeting, c.meeting_id) if c else None
        if not c or not meeting or meeting.organization_id != actor.organization_id:
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


@router.post("/chat/{peer_id}/attachments")
def attachments(
    peer_id: str, actor: User = Depends(current_user), db: Session = Depends(get_db)
):
    peer_user(db, actor, peer_id)
    raise HTTPException(
        501, "Attachments are planned for a later version. Upload is disabled."
    )
