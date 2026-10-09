import asyncio
from datetime import date
from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.core.database import Base
from app.core.config import settings
from app.services.commitments.dependency_graph import DependencyGraph
from app.services.commitments.intelligence import descendants, assess, serialize
from app.models.logs import AuthLog, GeneralLog, ErrorLog
from app.models import people, entities, integrations, email_actions
from app.main import app
from app.core import observability
from app.ai.provider import CompatibleProvider


@pytest.mark.parametrize("n", [0, 1, 10, 100])
def test_graph_matches_reference(n):
    edges = [
        SimpleNamespace(prerequisite_id=str(i), commitment_id=str(i + 1))
        for i in range(n)
    ]
    graph = DependencyGraph(edges)
    assert descendants("0", graph) == {str(i) for i in range(1, n + 1)}
    assert descendants("unknown", graph) == set()


def test_cycle_terminates():
    edges = [
        SimpleNamespace(prerequisite_id="a", commitment_id="b"),
        SimpleNamespace(prerequisite_id="b", commitment_id="a"),
    ]
    assert descendants("a", DependencyGraph(edges)) == {"a", "b"}


def test_logs_and_redaction(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "logs.db"),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(observability, "SessionLocal", lambda: Session(engine))
    client = TestClient(app)
    response = client.get("/api/auth/me?token=SECRET")
    assert response.status_code == 401
    assert response.headers["X-Request-ID"]
    client.post("/api/meetings", json={"transcript": "SECRET"})
    with Session(engine) as db:
        logs = list(db.scalars(select(AuthLog)))
        assert logs and all("SECRET" not in row.action for row in logs)
        assert list(db.scalars(select(ErrorLog)))
        assert all(row.timestamp and row.duration_ms >= 0 for row in logs)


@pytest.mark.parametrize(
    "provider,base,expected",
    [
        (
            "groq",
            "https://api.groq.com",
            "https://api.groq.com/openai/v1/chat/completions",
        ),
        (
            "openai",
            "https://api.openai.com",
            "https://api.openai.com/v1/chat/completions",
        ),
        ("compatible", "https://test/v1", "https://test/v1/chat/completions"),
    ],
)
def test_provider_replaceable(monkeypatch, provider, base, expected):
    monkeypatch.setattr(settings, "ai_provider", provider)
    monkeypatch.setattr(settings, "ai_base_url", base)
    monkeypatch.setattr(settings, "ai_api_key", "fake")

    async def run():
        p = CompatibleProvider()
        await p.client.aclose()

        def respond(request):
            assert str(request.url) == expected
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
                    ]
                },
            )

        p.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        assert await p.json("test", {}) == {"ok": True}
        await p.close()

    asyncio.run(run())


@pytest.mark.parametrize("response", ["[]", "broken", ""])
def test_invalid_provider_response(monkeypatch, response):
    monkeypatch.setattr(settings, "ai_api_key", "fake")

    async def run():
        p = CompatibleProvider()
        await p.client.aclose()
        p.client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"choices": [{"message": {"content": response}}]}
                )
            )
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as err:
            await p.json("test", {})
        assert err.value.status_code == 502
        await p.close()

    asyncio.run(run())


@pytest.fixture(autouse=True)
def isolate_proxy_environment(monkeypatch):
    for key in (
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
    ):
        monkeypatch.delenv(key, raising=False)


def test_successful_auth_and_activity_logs(tmp_path, monkeypatch):
    from app.core.database import get_db
    from app.models.people import Organization, User

    engine = create_engine(
        "sqlite:///" + str(tmp_path / "activity.db"),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Organization(id="test-org", name="Test"))
        db.flush()
        db.add(
            User(
                id="test-user",
                organization_id="test-org",
                password_hash=__import__(
                    "app.core.security", fromlist=["hash_password"]
                ).hash_password("TestPassword123!"),
                name="Tester",
                email="tester@example.com",
                team="QA",
                role="Engineer",
            )
        )
        db.commit()

    def sessions():
        with Session(engine, expire_on_commit=False) as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    monkeypatch.setattr(observability, "SessionLocal", lambda: Session(engine))
    app.dependency_overrides[get_db] = sessions
    try:
        client = TestClient(app)
        login = client.post(
            "/api/auth/login",
            json={"username": "Tester", "password": "TestPassword123!"},
        )
        assert login.status_code == 200
        response = client.post(
            "/api/meetings",
            headers={"Authorization": "Bearer " + login.json()["token"]},
            json={
                "title": "Test meeting",
                "held_on": str(date.today()),
                "transcript": "Tester: I'll ship tomorrow.",
            },
        )
        assert response.status_code == 201
        with Session(engine) as db:
            auth = db.scalar(select(AuthLog).where(AuthLog.status_code == 200))
            activity = db.scalar(select(GeneralLog))
            assert auth.user_id == activity.user_id == "test-user"
            assert activity.organization_id == "test-org"
            assert activity.action == "POST /api/meetings"
    finally:
        app.dependency_overrides.clear()
