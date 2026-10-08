from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import current_user
from app.models.people import User
from app.models.entities import Meeting
from fastapi import HTTPException
from app.services.meeting_deletion import deletion_plan, delete_meeting
from app.services.meeting_access_policy import require_workflow_access

router = APIRouter(prefix="/api", tags=["Meeting deletion"])


class DeleteConfirmation(BaseModel):
    expected_commitment_ids: list[str] = Field(max_length=100000)


@router.get("/meetings/{meeting_id}/deletion-preview")
def preview(
    meeting_id: str, db: Session = Depends(get_db), actor: User = Depends(current_user)
):
    require_workflow_access(
        db,
        actor,
        meeting_id,
    )
    return deletion_plan(db, meeting_id)


@router.delete("/meetings/{meeting_id}")
def remove(
    meeting_id: str,
    body: DeleteConfirmation,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    require_workflow_access(
        db,
        actor,
        meeting_id,
    )
    return delete_meeting(db, meeting_id, body.expected_commitment_ids)
