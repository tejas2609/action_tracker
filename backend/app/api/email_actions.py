from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

import httpx

from app.ai.provider import get_provider
from app.core.auth import current_user
from app.core.database import get_db
from app.models.people import User
from app.services import email_actions as service

router = APIRouter(prefix="/api", tags=["email actions"])


class AcceptProposal(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        value = value.strip()

        if len(value) < 3:
            raise ValueError("Enter a title of at least three characters.")

        return value


@router.post("/integrations/gmail/scan")
async def scan(
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
    ai=Depends(get_provider),
):
    try:
        return await service.scan(db, actor, ai)

    except httpx.HTTPError:
        raise HTTPException(
            502,
            "Cannot reach Gmail. Retry later.",
        ) from None


@router.get("/email-review")
def review(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.review_page(db, actor, page, page_size)


@router.get("/email-review/{id}/source")
async def source(
    id: str,
    response: Response,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    try:
        return await service.review_source(db, actor, id)

    except httpx.HTTPError:
        raise HTTPException(502, "Cannot read Gmail source.") from None


@router.post("/email-review/{id}/accept")
async def accept(
    id: str,
    body: AcceptProposal,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        return await service.accept(db, actor, id, body)

    except httpx.HTTPError:
        raise HTTPException(502, "Cannot read Gmail source.") from None


@router.delete("/email-review/{id}")
def reject(
    id: str,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.reject(db, actor, id)


@router.get("/commitments/{id}/emails")
def attachments(
    id: str,
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=20),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    return service.attachment_page(
        db,
        actor,
        id,
        page,
        page_size,
    )


@router.delete("/commitments/{id}/emails/{attachment_id}")
def remove_attachment(
    id: str,
    attachment_id: str,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.remove_attachment(db, actor, id, attachment_id)
