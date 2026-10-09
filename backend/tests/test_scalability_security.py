import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select, text, event
from sqlalchemy.orm import Session, sessionmaker
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.core.database import Base, get_db
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models import (
    entities,
    people,
    source_actions,
    email_actions,
    integrations,
    logs,
    security,
)
from app.models.people import Organization, User, Message, Conversation
from app.models.entities import Commitment, Dependency, Event, now
from app.models.source_actions import SourceInbox, CommitmentSource
from app.services.sources.source_ingestion import SourceIngestionService
from app.services.sources.source_actions import claim_next, execute_claim
from app.repositories.commitments import CommitmentRepository
from app.services.commitments.intelligence import assess
from app.services.commitments.dependency_graph import DependencyGraph
from app.services.people.authentication import AuthenticationService
from app.schemas.social import PasswordLogin
from app.schemas.sources import SourceMessage


@pytest.fixture
def data(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "data.db"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add_all(
            [Organization(id="org", name="One"), Organization(id="other", name="Other")]
        )
        db.flush()
        db.add_all(
            [
                User(
                    id="a",
                    organization_id="org",
                    name="Alice",
                    email="alice@test.example",
                    password_hash=hash_password("SecurePassword123!"),
                ),
                User(
                    id="b", organization_id="org", name="Bob", email="bob@test.example"
                ),
                User(
                    id="x",
                    organization_id="other",
                    name="Outsider",
                    email="outsider@test.example",
                ),
            ]
        )
        db.commit()
    yield factory, engine
    engine.dispose()


def payload(body="Please prepare the launch report tomorrow."):
    return dict(
        subject="Chat",
        thread_id="thread",
        sender=dict(id="b", name="Bob", email="bob@test.example"),
        recipient=dict(id="a", name="Alice", email="alice@test.example"),
        sent_at=now().isoformat(),
        timezone="UTC",
        body=body,
        context=[],
    )


def enqueue(factory, body=None, external="message", source="chat"):
    with factory() as db:
        actor = db.get(User, "a")
        p = payload() if body is None else payload(body)
        if source == "gmail":
            p["google_sub"] = "google-a"
        job = SourceIngestionService(db).enqueue(source, external, actor, p)
        db.commit()
        return job.id


class FakeAI:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def json(self, instruction, value):
        self.calls += 1
        return self.result


def decision(title="Prepare launch report"):
    return {
        "new_tasks": [
            dict(
                title=title,
                due_date=None,
                description="Bob assigned preparation of the launch report.",
                evidence="Please prepare the launch report tomorrow.",
                confidence=0.95,
            )
        ],
        "related": [],
    }


def process(factory, ai):
    with factory() as db:
        claim = claim_next(db)
    assert claim
    asyncio.run(execute_claim(factory, claim, ai))
    return claim


def test_password_hash_and_verification():
    value = hash_password("SecurePassword123!")
    assert verify_password("SecurePassword123!", value)
    assert not verify_password("bad", value)
    assert not verify_password("anything", "malformed")
    with pytest.raises(ValueError):
        hash_password("short")


def test_schema_rejects_invalid_timezone_and_extra_fields():
    p = payload()
    p["timezone"] = "invalid/timezone"
    with pytest.raises(ValueError):
        SourceMessage.model_validate(p)
    p = payload()
    p["secret"] = "unknown"
    with pytest.raises(ValueError):
        SourceMessage.model_validate(p)


def test_idempotent_ingestion_and_processing(data):
    factory, _ = data
    first = enqueue(factory)
    assert enqueue(factory) == first
    ai = FakeAI(decision())
    process(factory, ai)
    with factory() as db:
        assert db.get(SourceInbox, first).state == "processed"
        assert len(list(db.scalars(select(Commitment)))) == 1
        assert len(list(db.scalars(select(CommitmentSource)))) == 1
        assert claim_next(db) is None


def test_no_db_transaction_held_during_ai(data):
    factory, _ = data
    enqueue(factory)

    class Probe(FakeAI):
        async def json(self, instruction, value):
            # An independent writer must be able to commit while AI is waiting.
            with factory() as db:
                user = db.get(User, "b")
                user.team = "Changed"
                db.commit()
            return await super().json(instruction, value)

    process(factory, Probe(decision()))
    with factory() as db:
        assert db.get(User, "b").team == "Changed"


def test_failed_ai_retries_without_partial_tasks(data):
    factory, _ = data
    identifier = enqueue(factory)

    class Broken:
        async def json(self, *args):
            raise TimeoutError()

    process(factory, Broken())
    with factory() as db:
        job = db.get(SourceInbox, identifier)
        assert job.state == "queued" and job.attempts == 1 and not job.claim_token
        assert not list(db.scalars(select(Commitment)))
        assert job.last_error == "TimeoutError"


def test_claim_skips_busy_recipient_and_recovers_expiry(data):
    factory, _ = data
    first = enqueue(factory)
    second = enqueue(factory, external="second")
    with factory() as db:
        one = claim_next(db)
        assert one[0] == first
    with factory() as db:
        assert claim_next(db) is None
        job = db.get(SourceInbox, first)
        job.claimed_until = now() - timedelta(seconds=1)
        db.commit()
    with factory() as db:
        reclaimed = claim_next(db)
        assert reclaimed[0] == first and reclaimed[1] != one[1]
    asyncio.run(execute_claim(factory, one, FakeAI(decision())))
    with factory() as db:
        assert not list(db.scalars(select(Commitment)))


def test_evidence_and_candidate_scope_reject_foreign_links(data):
    factory, _ = data
    with factory() as db:
        db.add(
            Commitment(
                id="foreign",
                organization_id="other",
                owner_id="x",
                owner="Outsider",
                title="Launch report",
                source_statement="Secret",
            )
        )
        db.commit()
    enqueue(factory)
    bad = {
        "new_tasks": [],
        "related": [
            dict(
                commitment_id="foreign",
                description="Link task",
                evidence="Please prepare the launch report tomorrow.",
                confidence=1,
            )
        ],
    }
    process(factory, FakeAI(bad))
    with factory() as db:
        assert not list(db.scalars(select(CommitmentSource)))


def test_encryption_roundtrip_and_raw_database(data, monkeypatch):
    factory, engine = data
    monkeypatch.setattr(
        settings, "data_encryption_keys", Fernet.generate_key().decode()
    )
    identifier = enqueue(factory)
    with engine.connect() as conn:
        value = conn.scalar(
            text("SELECT payload FROM source_inbox WHERE id=:id"), {"id": identifier}
        )
        assert "launch report" not in value and "_encrypted_v1" in value
    with factory() as db:
        assert db.get(SourceInbox, identifier).payload["body"] == payload()["body"]
    process(factory, FakeAI(decision()))
    with factory() as db:
        assert db.get(SourceInbox, identifier).state == "processed"


def test_database_risk_matches_domain_and_page_bounds(data):
    factory, _ = data
    with factory() as db:
        for i in range(40):
            db.add(
                Commitment(
                    id=str(i),
                    organization_id="org",
                    owner_id="a",
                    owner="Alice",
                    title="Task " + str(i),
                    source_statement="Source",
                    due_date=date.today() + timedelta(days=(i % 8) - 3),
                    progress=i % 101,
                    blocker="Blocked" if i % 3 == 0 else "",
                    condition="Approval" if i % 5 == 0 else "",
                    condition_met=False,
                    status="completed" if i % 7 == 0 else "active",
                )
            )
        db.commit()
        repo = CommitmentRepository(db, db.get(User, "a"))
        for state in (
            "all",
            "high",
            "medium",
            "low",
            "waiting",
            "overdue",
            "attention",
            "completed",
        ):
            page = repo.page(repo.filtered("mine", "", state), 1, 5)
            assert len(page["items"]) <= 5
            for item in page["items"]:
                c = db.get(Commitment, item["id"])
                expected = assess(c, {c.id: c}, DependencyGraph([]))
                assert item["risk"] == expected
                if state in ("high", "medium", "low"):
                    assert expected["level"] == state
        assert repo.page(repo.filtered(), 1, 5)["total"] == 40


@pytest.mark.parametrize("scope", ["mine", "organization"])
def test_commitment_listing_excludes_cancelled_before_pagination(data, scope):
    from app.services.commitments.commitment_api import commitments

    factory, _ = data
    with factory() as db:
        for identifier, status in (
            ("0-cancelled", "cancelled"),
            ("1-active", "active"),
            ("2-completed", "completed"),
            ("3-review", "review"),
        ):
            db.add(
                Commitment(
                    id=identifier,
                    organization_id="org",
                    owner_id="a",
                    owner="Alice",
                    title="Task " + identifier,
                    source_statement="Source",
                    status=status,
                )
            )
        db.commit()
        workflow = SimpleNamespace(s=SimpleNamespace(db=db, actor=db.get(User, "a")))
        for state in ("all", "low"):
            pages = [
                commitments(scope=scope, state=state, page=page, page_size=1, s=workflow)
                for page in (1, 2, 3)
            ]
            assert [page["total"] for page in pages] == [2, 2, 2]
            assert [item["id"] for page in pages for item in page["items"]] == [
                "1-active",
                "2-completed",
            ]
            assert pages[2]["items"] == []
        cancelled = commitments(
            scope=scope, state="cancelled", page=1, page_size=10, s=workflow
        )
        assert cancelled["items"] == [] and cancelled["total"] == 0
        assert db.get(Commitment, "0-cancelled").status == "cancelled"


def test_login_rate_limit_and_no_wildcard_impersonation(data, monkeypatch):
    factory, _ = data
    monkeypatch.setattr(settings, "login_attempts_per_minute", 3)
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"), state=SimpleNamespace()
    )
    with factory() as db:
        service = AuthenticationService(db)
        for _ in range(3):
            with pytest.raises(HTTPException) as error:
                service.login(
                    PasswordLogin(username="%", password="SecurePassword123!"), request
                )
            assert error.value.status_code == 401
        with pytest.raises(HTTPException) as error:
            service.login(PasswordLogin(username="%", password="wrong"), request)
        assert error.value.status_code == 429


def test_gmail_projection_uses_shared_processing(data):
    factory, _ = data
    from app.models.integrations import GmailConnection

    with factory() as db:
        db.add(
            GmailConnection(
                user_id="a",
                google_sub="google-a",
                email="alice@test.example",
                name="Alice",
                scopes="scope",
                access_token_encrypted="encrypted",
                refresh_token_encrypted="encrypted",
                expires_at=now() + timedelta(hours=1),
                connected_at=now(),
            )
        )
        db.commit()
    enqueue(factory, source="gmail")
    process(factory, FakeAI(decision()))
    with factory() as db:
        from app.models.email_actions import EmailOrigin, CommitmentEmail

        assert db.scalar(select(EmailOrigin)).description
        assert db.scalar(select(CommitmentEmail)).body_text == payload()["body"]
        assert db.scalar(select(SourceInbox)).state == "processed"


def test_no_sensitive_validation_echo_and_body_limit(monkeypatch):
    from app.main import app
    from app.core import observability

    monkeypatch.setattr(observability, "persist", lambda records: None)
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "test", "password": "secret", "unrecognized": "PRIVATE"},
        )
        assert (
            response.status_code == 422
            and "PRIVATE" not in response.text
            and "secret" not in response.text
        )
        monkeypatch.setattr(settings, "max_request_bytes", 20)
        response = client.post("/api/auth/login", content=b"x" * 21)
        assert response.status_code == 413
        assert client.get("/api/health").headers["x-content-type-options"] == "nosniff"


def test_authenticated_api_end_to_end(data, monkeypatch):
    factory, engine = data
    from app.main import app
    from app.ai.provider import get_provider
    from app.core import observability
    from app.models.people import LoginSession

    fake = FakeAI(
        {
            "findings": [
                {
                    "kind": "commitment",
                    "title": "Prepare launch report",
                    "owner": "Alice",
                    "source_line": 1,
                    "statement": "source",
                    "due_date": None,
                    "condition": "",
                    "confidence": 0.95,
                    "explanation": "",
                    "existing_id": None,
                    "depends_on_indices": [],
                    "prerequisite_ids": [],
                }
            ]
        }
    )

    def sessions():
        with factory() as db:
            try:
                yield db
            finally:
                db.rollback()

    app.dependency_overrides[get_db] = sessions
    app.dependency_overrides[get_provider] = lambda: fake
    monkeypatch.setattr(observability, "SessionLocal", factory)
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/auth/login",
                json={
                    "username": "alice@test.example",
                    "password": "SecurePassword123!",
                },
            )
            assert login.status_code == 200
            headers = {"Authorization": "Bearer " + login.json()["token"]}
            meeting = client.post(
                "/api/meetings",
                headers=headers,
                json={
                    "title": "Launch",
                    "held_on": str(date.today()),
                    "transcript": "Alice: I'll prepare the launch report.",
                    "participant_ids": ["b"],
                },
            )
            assert meeting.status_code == 201, meeting.text
            mid = meeting.json()["id"]
            analyzed = client.post(f"/api/meetings/{mid}/analyze", headers=headers)
            assert analyzed.status_code == 200, analyzed.text
            reviewed = client.post(
                f"/api/meetings/{mid}/review",
                headers=headers,
                json={
                    "items": [
                        {
                            "index": 0,
                            "action": "confirm",
                            "title": "Prepare launch report",
                            "owner": "Alice",
                            "owner_id": "a",
                        }
                    ]
                },
            )
            assert reviewed.status_code == 200, reviewed.text
            assert (
                client.post(
                    f"/api/meetings/{mid}/review",
                    headers=headers,
                    json={
                        "items": [
                            {
                                "index": 0,
                                "action": "ignore",
                                "title": "Ignored",
                                "owner": "Alice",
                            }
                        ]
                    },
                ).status_code
                == 409
            )
            listing = client.get("/api/commitments", headers=headers)
            assert listing.status_code == 200 and listing.json()["total"] == 1
            identifier = listing.json()["items"][0]["id"]
            updated = client.patch(
                f"/api/commitments/{identifier}", headers=headers, json={"progress": 20}
            )
            assert updated.status_code == 200, updated.text
            assert (
                client.get("/api/dashboard", headers=headers).json()["metrics"][
                    "active"
                ]
                == 1
            )
            assert (
                client.get(
                    f"/api/commitments/{identifier}", headers=headers
                ).status_code
                == 200
            )
            sent = client.post(
                "/api/chat/b",
                headers=headers,
                json={
                    "body": "Please finish the launch report.",
                    "commitment_id": identifier,
                },
            )
            assert sent.status_code == 201, sent.text
            assert client.get("/api/chat/b", headers=headers).status_code == 200
            assert client.post("/api/auth/logout", headers=headers).status_code == 200
            assert client.get("/api/auth/me", headers=headers).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_source_review_accept_and_structured_update(data, monkeypatch):
    factory, engine = data
    from app.main import app
    from app.core import observability
    from app.core.auth import current_user

    def sessions():
        with factory() as db:
            try:
                yield db
            finally:
                db.rollback()

    def actor():
        with factory() as db:
            return db.get(User, "a")

    app.dependency_overrides[get_db] = sessions
    app.dependency_overrides[current_user] = actor
    monkeypatch.setattr(observability, "SessionLocal", factory)
    try:
        enqueue(factory)
        process(factory, FakeAI(decision()))
        with TestClient(app) as client:
            review = client.get("/api/source-review")
            assert review.status_code == 200 and review.json()["total"] == 1
            identifier = review.json()["items"][0]["id"]
            assert (
                client.post(
                    f"/api/source-review/{identifier}/accept",
                    json={"title": "Prepare launch report"},
                ).status_code
                == 200
            )
            message = "The deadline is now 2026-12-01."
            enqueue(factory, body=message, external="update")
            ai = FakeAI(
                {
                    "new_tasks": [],
                    "related": [
                        {
                            "commitment_id": identifier,
                            "description": "Deadline revised explicitly.",
                            "evidence": message,
                            "confidence": 0.99,
                            "proposed_changes": {"due_date": "2026-12-01"},
                        }
                    ],
                }
            )
            process(factory, ai)
            sources = client.get(f"/api/commitments/{identifier}/sources").json()[
                "items"
            ]
            link = next(item for item in sources if item["proposed_changes"])
            assert (
                client.post("/api/source-updates/" + link["id"] + "/apply").status_code
                == 200
            )
            assert (
                client.post("/api/source-updates/" + link["id"] + "/apply").status_code
                == 409
            )
            with factory() as db:
                assert db.get(Commitment, identifier).due_date == date(2026, 12, 1)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def meeting_assignment_client(data, monkeypatch):
    from app.main import app
    from app.core.auth import current_user
    from app.core import observability
    from app.models.entities import Meeting, MeetingParticipant

    factory, _ = data
    with factory() as db:
        for identifier, organization, visibility in (
            ("public", "org", "public"),
            ("another-public", "org", "public"),
            ("private", "org", "private"),
            ("foreign", "other", "public"),
        ):
            db.add(Meeting(
                id=identifier, organization_id=organization,
                title=identifier, held_on=date.today(),
                transcript="Bob: Restricted transcript content.",
                visibility=visibility,
            ))
        db.flush()
        db.add(MeetingParticipant(meeting_id="public", user_id="b"))
        for identifier, organization, owner, status in (
            ("mine", "org", "a", "active"),
            ("others", "org", "b", "active"),
            ("foreign-task", "other", "x", "active"),
            ("review-task", "org", "a", "review"),
        ):
            db.add(Commitment(
                id=identifier, organization_id=organization, owner_id=owner,
                owner=db.get(User, owner).name, title=identifier,
                source_statement="Original source", status=status,
            ))
        db.commit()

    identity = {"id": "a"}

    def sessions():
        with factory() as db:
            try:
                yield db
            finally:
                db.rollback()

    def actor():
        with factory() as db:
            return db.get(User, identity["id"])

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = sessions
    app.dependency_overrides[current_user] = actor
    monkeypatch.setattr(observability, "SessionLocal", factory)
    try:
        with TestClient(app) as client:
            yield client, factory, identity
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_assign_public_meeting_and_preserve_transcript_access(meeting_assignment_client):
    client, factory, identity = meeting_assignment_client
    directory = client.get("/api/meeting-directory?page_size=1").json()
    assert directory["total"] == 2 and len(directory["items"]) == 1
    second = client.get("/api/meeting-directory?page_size=1&page=2").json()
    assert {row["id"] for row in directory["items"] + second["items"]} == {
        "public", "another-public",
    }
    assert all("transcript" not in row and "findings" not in row for row in directory["items"])
    response = client.post("/api/commitments/mine/meeting", json={"meeting_id": "public"})
    assert response.status_code == 200, response.text
    assert response.json() == {"id": "mine", "meeting_id": "public"}
    detail = client.get("/api/commitments/mine")
    assert detail.status_code == 200, detail.text
    assert detail.json()["meeting"] == {
        "id": "public", "title": "public", "held_on": str(date.today()),
    }
    assert detail.json()["source_statement"] == "Original source"
    assert client.get("/api/meeting-agendas/public").status_code == 404
    assert client.post(
        "/api/commitments/mine/meeting", json={"meeting_id": "another-public"}
    ).status_code == 409
    with factory() as db:
        assert db.get(Commitment, "mine").meeting_id == "public"
        events = list(db.scalars(select(Event).where(Event.commitment_id == "mine")))
        assert len(events) == 1
        assert events[0].kind == "meeting_assigned" and events[0].meeting_id == "public"
    identity["id"] = "b"
    agenda = client.get("/api/meeting-agendas/public")
    assert agenda.status_code == 200, agenda.text
    assert {item["id"] for item in agenda.json()["within"]["nodes"]} == {"mine"}


@pytest.mark.parametrize("commitment_id,meeting_id,status", [
    ("mine", "private", 404),
    ("mine", "foreign", 404),
    ("mine", "missing", 404),
    ("others", "public", 403),
    ("foreign-task", "public", 404),
    ("review-task", "public", 404),
])
def test_meeting_assignment_rejects_ineligible_records(
    meeting_assignment_client, commitment_id, meeting_id, status
):
    client, factory, _ = meeting_assignment_client
    response = client.post(
        f"/api/commitments/{commitment_id}/meeting", json={"meeting_id": meeting_id}
    )
    assert response.status_code == status, response.text
    with factory() as db:
        assert db.get(Commitment, commitment_id).meeting_id is None
        assert not list(db.scalars(select(Event)))


def test_product_manager_can_assign_another_owners_commitment(meeting_assignment_client):
    client, factory, identity = meeting_assignment_client
    with factory() as db:
        db.get(User, "b").role = "Product Manager"
        db.commit()
    identity["id"] = "b"
    response = client.post("/api/commitments/mine/meeting", json={"meeting_id": "public"})
    assert response.status_code == 200, response.text
    with factory() as db:
        c = db.get(Commitment, "mine")
        assert c.owner_id == "a" and c.meeting_id == "public"


def test_batch_cycle_check():
    graph = DependencyGraph([SimpleNamespace(prerequisite_id="a", commitment_id="b")])
    assert not graph.has_cycle([("b", "c")])
    assert graph.has_cycle([("b", "c"), ("c", "a")])
    assert graph.has_cycle([("z", "z")])
