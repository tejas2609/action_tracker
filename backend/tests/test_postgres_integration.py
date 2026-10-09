"""Opt-in tests isolated in a temporary schema of TEST_POSTGRES_URL."""

import os, uuid
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from app.models.people import Organization, User
from app.models.entities import Commitment
from app.models.source_actions import SourceInbox
from app.services.sources.source_actions import claim_next
from app.services.sources.source_candidates import find_candidates
from app.services.sources.source_ingestion import SourceIngestionService
from app.models.entities import now


@pytest.fixture
def pg():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set TEST_POSTGRES_URL to run PostgreSQL integration tests")
    schema = "test_" + uuid.uuid4().hex
    control = create_engine(url)
    with control.begin() as connection:
        connection.execute(text("CREATE SCHEMA " + schema))
    engine = create_engine(url, connect_args={"options": "-c search_path=" + schema})
    try:
        with engine.begin() as connection:
            config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            config.set_main_option(
                "script_location", str(Path(__file__).parents[1] / "migrations")
            )
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        factory = sessionmaker(engine, expire_on_commit=False)
        yield factory, engine
    finally:
        engine.dispose()
        with control.begin() as connection:
            connection.execute(text("DROP SCHEMA " + schema + " CASCADE"))
        control.dispose()


@pytest.mark.postgres
def test_full_migrations_and_indexed_candidates(pg):
    factory, engine = pg
    with factory() as db:
        actor = db.scalar(select(User).where(User.name == "Tejas"))
        db.add_all(
            [
                Commitment(
                    title="Prepare launch report",
                    owner=actor.name,
                    owner_id=actor.id,
                    organization_id=actor.organization_id,
                    source_statement="Launch report assigned",
                ),
                Commitment(
                    title="Unrelated finance review",
                    owner=actor.name,
                    owner_id=actor.id,
                    organization_id=actor.organization_id,
                    source_statement="Budget",
                ),
            ]
        )
        db.commit()
        rows = find_candidates(db, actor, "launch report")
        assert [row.title for row in rows] == ["Prepare launch report"]
        db.execute(text("SET LOCAL enable_seqscan=off"))
        explain = db.execute(
            text(
                "EXPLAIN SELECT * FROM commitments WHERE to_tsvector('english'::regconfig, coalesce(title, '') || ' ' || coalesce(source_statement, '')) @@ to_tsquery('english', 'launch')"
            )
        ).all()
        assert "ix_commitments_search_gin" in str(explain)
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "010"


@pytest.mark.postgres
def test_claim_does_not_hold_connection_and_serializes_recipient(pg):
    factory, engine = pg
    with factory() as db:
        actor = db.scalar(select(User).where(User.name == "Tejas"))
        payload = {
            "subject": "Chat",
            "thread_id": "thread",
            "sender": {"id": "sender", "name": "Sender", "email": ""},
            "recipient": {"id": actor.id, "name": actor.name, "email": actor.email},
            "sent_at": now().isoformat(),
            "timezone": "UTC",
            "body": "Prepare launch report.",
            "context": [],
        }
        for external in ("one", "two"):
            SourceIngestionService(db).enqueue("chat", external, actor, payload)
        db.commit()
    with factory() as db:
        assert claim_next(db)
    with factory() as db:
        assert claim_next(db) is None
    assert engine.pool.checkedout() == 0
