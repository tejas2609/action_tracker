from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.people import Organization, User
from app.repositories.store import Store
from app.services.team_deadlines import team_missed_deadlines


@pytest.fixture
def team():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Organization(id="org", name="Org"), Organization(id="other", name="Other")])
        db.flush()
        manager = User(id="manager", organization_id="org", name="Manager", email="manager@test", is_manager=True)
        db.add(manager)
        db.flush()
        for id, org, active, manager_id in [
            ("report", "org", True, "manager"),
            ("outsider", "org", True, None),
            ("foreign", "other", True, "manager"),
            ("inactive", "org", False, "manager"),
            ("nested", "org", True, "report"),
        ]:
            db.add(User(id=id, organization_id=org, name=id.title(), email=id + "@test", active=active, manager_id=manager_id))
        db.flush()
        today = date.today()
        def row(id, owner="report", days=-1, status="active", blocked=False):
            return {
                "id": id, "owner_id": owner, "owner": owner.title(), "title": id,
                "due_date": today + timedelta(days=days) if days is not None else None,
                "status": status, "progress": 20,
                "risk": {"state": "waiting" if blocked else "overdue", "level": "high"},
            }
        rows = [row("task" + str(i), days=-10+i, blocked=i == 0) for i in range(7)]
        rows += [row("own", "manager"), row("outside", "outsider"), row("foreign", "foreign"),
                 row("inactive", "inactive"), row("nested", "nested"), row("today", days=0),
                 row("future", days=1), row("undated", days=None),
                 row("completed", status="completed"), row("cancelled", status="cancelled")]
        yield SimpleNamespace(s=Store(db, manager), listing=lambda: rows)


def test_scope_top_five_and_pagination(team):
    result = team_missed_deadlines(team, page_size=5)
    assert result["total"] == 7
    assert [c["id"] for c in result["items"]] == ["task" + str(i) for i in range(5)]
    assert result["members"] == [{"id": "report", "name": "Report"}]
    result = team_missed_deadlines(team, page=99, page_size=5)
    assert result["page"] == 2
    assert [c["id"] for c in result["items"]] == ["task5", "task6"]


def test_filters_sort_and_empty_page(team):
    result = team_missed_deadlines(team, blocked="yes")
    assert [c["id"] for c in result["items"]] == ["task0"]
    result = team_missed_deadlines(team, q=" TASK ", blocked="no", direction="desc",
                                   due_from=date.today() - timedelta(days=5))
    assert [c["id"] for c in result["items"]] == ["task6", "task5"]
    result = team_missed_deadlines(team, owner_id="outsider", page=5)
    assert result["total"] == 0 and result["page"] == 1


def test_non_manager_rejected(team):
    team.s.actor.is_manager = False
    with pytest.raises(HTTPException) as error:
        team_missed_deadlines(team)
    assert error.value.status_code == 403


def test_invalid_date_range(team):
    with pytest.raises(HTTPException) as error:
        team_missed_deadlines(team, due_from=date.today(), due_to=date.today() - timedelta(days=1))
    assert error.value.status_code == 422


def test_http_validation_and_manager_dashboard(team):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.routes import service

    app.dependency_overrides[service] = lambda: team
    try:
        with TestClient(app) as client:
            response = client.get("/api/team-missed-deadlines?page_size=5&page=2")
            assert response.status_code == 200
            assert response.json()["total"] == 7
            assert len(response.json()["items"]) == 2
            for params in ["sort=invalid", "direction=invalid", "blocked=invalid", "page=0", "page_size=101", "due_from=invalid"]:
                assert client.get("/api/team-missed-deadlines?" + params).status_code == 422
            dashboard = client.get("/api/dashboard?page_size=100").json()
            assert len(dashboard["team_missed"]["items"]) == 5
            assert dashboard["team_missed"]["total"] == 7
            assert dashboard["metrics"]["total"] == 1
            team.s.actor.is_manager = False
            assert client.get("/api/team-missed-deadlines").status_code == 403
            assert client.get("/api/dashboard").json()["team_missed"] is None
    finally:
        app.dependency_overrides.pop(service, None)
