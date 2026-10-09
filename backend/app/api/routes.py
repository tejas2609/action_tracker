from app.core.async_bridge import run_legacy
from fastapi import APIRouter, Depends, Query
from datetime import date
from typing import Literal
from app.schemas.contracts import (
    MeetingInput,
    Review,
    Update,
    EdgeInput,
    SearchInput,
    FollowupInput,
    AssignMeeting,
)
from app.services.commitments import commitment_api as operations
from app.api.dependencies import service
from app.schemas.contracts import ManualCommitmentInput
from app.services.commitments.commitment_api import (
    create_manual_commitment,
    meeting_options,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return operations.health()


@router.get("/commitments")
def commitments(
    scope: str = "mine",
    q: str = Query("", max_length=200),
    state: str = "all",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    s=Depends(service),
):
    return operations.commitments(
        scope=scope, q=q, state=state, page=page, page_size=page_size, s=s
    )


@router.post("/commitments", status_code=201)
def create_commitment(
    body: ManualCommitmentInput,
    s=Depends(service),
):
    return create_manual_commitment(s, body)


@router.get("/meeting-options")
def list_meeting_options(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    s=Depends(service),
):
    return meeting_options(s.s, page, page_size)


@router.post("/commitments/{id}/meeting")
def assign_meeting(id: str, body: AssignMeeting, s=Depends(service)):
    return s.assign_meeting(id, body.meeting_id)


@router.get("/team-missed-deadlines")
def team_deadlines(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: str = Query("", max_length=200),
    owner_id: str = "",
    due_from: date | None = None,
    due_to: date | None = None,
    blocked: Literal["all", "yes", "no"] = "all",
    sort: Literal["due_date", "owner", "title", "progress"] = "due_date",
    direction: Literal["asc", "desc"] = "asc",
    s=Depends(service),
):
    return operations.team_deadlines(
        page=page,
        page_size=page_size,
        q=q,
        owner_id=owner_id,
        due_from=due_from,
        due_to=due_to,
        blocked=blocked,
        sort=sort,
        direction=direction,
        s=s,
    )


@router.get("/dashboard")
def dashboard(
    missed_page: int = Query(1, ge=1),
    upcoming_page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=100),
    s=Depends(service),
):
    return operations.dashboard(
        missed_page=missed_page, upcoming_page=upcoming_page, page_size=page_size, s=s
    )


@router.get("/graph")
def graph(mode: str = "immediate", s=Depends(service)):
    return operations.graph(mode=mode, s=s)


@router.get("/meetings")
def meetings(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    s=Depends(service),
):
    return operations.meetings(s=s, page=page, page_size=page_size)


@router.post("/meetings", status_code=201)
def create_meeting(body: MeetingInput, s=Depends(service)):
    return operations.create_meeting(body=body, s=s)


@router.post("/meetings/{id}/analyze")
async def analyze(id: str, s=Depends(service)):
    return await run_legacy(operations.analyze, id=id, s=s)


@router.post("/meetings/{id}/review")
def review(id: str, body: Review, s=Depends(service)):
    return operations.review(id=id, body=body, s=s)


@router.get("/commitments/{id}")
def detail(id: str, s=Depends(service)):
    return operations.detail(id=id, s=s)


@router.patch("/commitments/{id}")
def update(id: str, body: Update, s=Depends(service)):
    return operations.update(id=id, body=body, s=s)


@router.post("/commitments/{id}/dependencies", status_code=201)
def edge(id: str, body: EdgeInput, s=Depends(service)):
    return operations.edge(id=id, body=body, s=s)


@router.delete("/commitments/{id}/dependencies/{pre}")
def remove_edge(id: str, pre: str, s=Depends(service)):
    return operations.remove_edge(id=id, pre=pre, s=s)


@router.post("/commitments/{id}/dependencies/{pre}/replace")
def replace_edge(id: str, pre: str, body: EdgeInput, s=Depends(service)):
    return operations.replace_edge(id=id, pre=pre, body=body, s=s)


@router.post("/commitments/{id}/followup")
async def followup(id: str, body: FollowupInput | None = None, s=Depends(service)):
    return await run_legacy(operations.followup, id=id, body=body, s=s)


@router.post("/commitments/{id}/analysis")
async def blocker_analysis(id: str, s=Depends(service)):
    return await run_legacy(operations.blocker_analysis, id=id, s=s)


@router.post("/search")
async def search(body: SearchInput, s=Depends(service)):
    return await run_legacy(operations.search, body=body, s=s)


@router.get("/ready")
def readiness():
    from app.core.database import engine
    from sqlalchemy import text
    from fastapi import HTTPException

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ready"}


@router.get("/commitments/{id}/events")
def history(
    id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    s=Depends(service),
):
    from app.models.entities import Event, Commitment
    from sqlalchemy import select
    from sqlalchemy import func

    s.s.get(Commitment, id)
    query = select(Event).where(Event.commitment_id == id)
    total = s.s.db.scalar(select(func.count()).select_from(query.subquery()))
    items = list(
        s.s.db.scalars(
            query.order_by(Event.created_at.desc(), Event.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}
