from app.schemas.profile import ProfileUpdate
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.auth import current_user
from app.core.database import get_db
from app.models.people import User
from app.services import profile as operations

router = APIRouter(prefix="/api/profile", tags=["Profile"])


@router.get("")
def get_profile(actor: User = Depends(current_user), db: Session = Depends(get_db)):
    return operations.get_profile(actor=actor, db=db)


@router.patch("")
def update_profile(
    body: ProfileUpdate,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.update_profile(body=body, actor=actor, db=db)


@router.post("/team/{user_id}")
def add_member(
    user_id: str, actor: User = Depends(current_user), db: Session = Depends(get_db)
):
    return operations.add_member(user_id=user_id, actor=actor, db=db)


@router.delete("/team/{user_id}")
def remove_member(
    user_id: str, actor: User = Depends(current_user), db: Session = Depends(get_db)
):
    return operations.remove_member(user_id=user_id, actor=actor, db=db)
