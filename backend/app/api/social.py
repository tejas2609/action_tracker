from app.schemas.social import PasswordLogin, MessageInput
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import current_user, security
from fastapi.security import HTTPAuthorizationCredentials
from app.models.people import User
from app.services import social as operations
from app.services.social import public_user as public_user

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
    q: str = "",
    team: str = "",
    role: str = "",
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.users(q=q, team=team, role=role, actor=actor, db=db)


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
