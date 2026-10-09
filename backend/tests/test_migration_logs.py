"""Exercise revision 006 independently of older PostgreSQL-only migrations."""

import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, MetaData, Table, Column, String, DateTime, inspect


def test_006_upgrade_downgrade():
    path = Path(__file__).parents[1] / "migrations/versions/006_logs_indexes.py"
    spec = importlib.util.spec_from_file_location("migration_006", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    metadata = MetaData()
    for name, cols in [
        ("events", ["commitment_id", "created_at"]),
        ("dependencies", ["prerequisite_id"]),
        ("commitments", ["organization_id", "owner_id", "status"]),
        ("messages", ["conversation_id", "created_at", "id"]),
    ]:
        Table(name, metadata, *[Column(col, String()) for col in cols])
    metadata.create_all(engine)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            inspector = inspect(connection)
            assert {"auth_logs", "general_logs", "error_logs"} <= set(
                inspector.get_table_names()
            )
            assert len(inspector.get_indexes("events")) == 1
            module.downgrade()
            assert "error_logs" not in inspect(connection).get_table_names()


def test_010_additive_upgrade_downgrade():
    path = Path(__file__).parents[1] / "migrations/versions/010_scalability_security.py"
    spec = importlib.util.spec_from_file_location("migration_010", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    metadata = MetaData()
    for name, cols in [
        ("users", ["id"]),
        ("commitment_sources", ["id"]),
        ("source_inbox", ["id", "recipient_id", "source", "state"]),
        ("commitments", ["id", "organization_id", "due_date"]),
        ("login_sessions", ["expires_at"]),
    ]:
        Table(name, metadata, *[Column(col, String()) for col in cols])
    metadata.create_all(engine)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "password_hash" in {
                c["name"] for c in inspect(connection).get_columns("users")
            }
            assert "claimed_until" in {
                c["name"] for c in inspect(connection).get_columns("source_inbox")
            }
            module.downgrade()
            assert "password_hash" not in {
                c["name"] for c in inspect(connection).get_columns("users")
            }
