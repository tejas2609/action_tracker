"""Thin API layer: dependency injection and request validation only."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app.core.auth import current_user
from app.core.database import get_db
from app.models.people import User
from app.services.sources import source_review as operations
from app.services.sources.source_review import AcceptSource

router = APIRouter(prefix="/api", tags=["Source commitments"])


@router.get("/source-review")
def review(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.review(
        response=response, page=page, page_size=page_size, actor=actor, db=db
    )


@router.post("/source-review/{id}/accept")
def accept(
    id: str,
    body: AcceptSource,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.accept(id=id, body=body, actor=actor, db=db)


@router.delete("/source-review/{id}")
def reject(
    id: str,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.reject(id=id, actor=actor, db=db)


@router.get("/commitments/{id}/sources")
def sources(
    id: str,
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return operations.sources(
        id=id, response=response, page=page, page_size=page_size, actor=actor, db=db
    )


@router.post("/source-updates/{link_id}/apply")
def apply_update(
    link_id: str, actor: User = Depends(current_user), db: Session = Depends(get_db)
):
    return operations.apply_update(link_id=link_id, actor=actor, db=db)
