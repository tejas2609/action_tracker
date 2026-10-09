from app.schemas.social import PasswordLogin, MessageInput
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import current_user, security
from fastapi.security import HTTPAuthorizationCredentials
from app.models.people import User
from app.services.people import social as operations
from app.services.people.social import public_user as public_user
from pydantic import Field
from app.schemas.base import StrictModel
from app.services.people import chat_inbox

router = APIRouter(prefix="/api", tags=["Users and chat"])


@router.get("/messaging/capabilities")
def capabilities(actor: User = Depends(current_user)):
    return operations.capabilities(actor=actor)


@router.post("/auth/login")
def password_login(
    body: PasswordLogin, request: Request, db: Session = Depends(get_db)
):
    return operations.password_login(body=body, db=db, request=request)


@router.get("/auth/me")
def me(actor: User = Depends(current_user)):
    return operations.me(actor=actor)


@router.post("/auth/logout")
def logout(
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    return operations.logout(actor=actor, db=db, credentials=credentials)


@router.get("/users")
def users(
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    team: str = "",
    role: str = "",
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.users(
        q=q, team=team, role=role, actor=actor, db=db, page=page, page_size=page_size
    )


@router.get("/chat/{peer_id}")
def get_chat(
    peer_id: str,
    before: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.get_chat(
        peer_id=peer_id, before=before, limit=limit, actor=actor, db=db
    )


@router.post("/chat/{peer_id}", status_code=201)
def send(
    peer_id: str,
    body: MessageInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.send(peer_id=peer_id, body=body, actor=actor, db=db)


@router.post("/chat/{peer_id}/attachments")
def attachments(
    peer_id: str, actor: User = Depends(current_user), db: Session = Depends(get_db)
):
    return operations.attachments(peer_id=peer_id, actor=actor, db=db)


class MarkChatRead(StrictModel):
    through_id: str = Field(min_length=1, max_length=36)


@router.get("/chat-inbox")
def list_chat_inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return chat_inbox.inbox(db, actor, page, page_size)


@router.post("/chat/{peer_id}/read")
def read_chat(
    peer_id: str,
    body: MarkChatRead,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return chat_inbox.mark_read(
        db,
        actor,
        peer_id,
        body.through_id,
    )
