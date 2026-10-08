from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import service

from .repository import AgendaRepository
from .service import AgendaService

router = APIRouter(
    prefix="/api/meeting-agendas",
    tags=["meeting-agendas"],
)


def agendas(workflow=Depends(service)):
    return AgendaService(AgendaRepository(workflow.s))


@router.get("")
def list_agendas(
    tab: Literal["active", "completed"] = "active",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    svc=Depends(agendas),
):
    return svc.list(tab, page, page_size)


@router.get("/{meeting_id}")
def agenda_detail(
    meeting_id: str,
    svc=Depends(agendas),
):
    return svc.detail(meeting_id)
