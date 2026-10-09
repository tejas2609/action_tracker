"""Credentials, worker leases and indexed retrieval; additive upgrade."""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009_source_actions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "commitment_sources",
        sa.Column(
            "proposed_changes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(255), nullable=False, server_default=""),
    )
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(80), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "source_inbox",
        sa.Column("thread_id", sa.String(255), nullable=False, server_default=""),
    )
    op.add_column(
        "source_inbox", sa.Column("claim_token", sa.String(36), nullable=True)
    )
    op.add_column(
        "source_inbox",
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_source_inbox_thread_id", "source_inbox", ["thread_id"])
    op.create_index(
        "ix_source_recipient_thread",
        "source_inbox",
        ["recipient_id", "source", "thread_id"],
    )
    op.create_index("ix_source_lease", "source_inbox", ["state", "claimed_until"])
    op.create_index(
        "ix_commitments_org_due_id",
        "commitments",
        ["organization_id", "due_date", "id"],
    )
    op.create_index("ix_sessions_expiry", "login_sessions", ["expires_at"])
    op.create_table(
        "login_throttles",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("bucket", sa.Integer(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE source_inbox SET thread_id = coalesce(payload->>'thread_id', '')"
        )
        op.execute(
            "CREATE INDEX ix_commitments_search_gin ON commitments USING gin (to_tsvector('english'::regconfig, coalesce(title, '') || ' ' || coalesce(source_statement, '')))"
        )
        op.execute("CREATE INDEX ix_users_lower_email ON users (lower(email))")
        op.execute("CREATE INDEX ix_users_lower_name ON users (lower(name))")


def downgrade():
    op.drop_column("commitment_sources", "proposed_changes")
    if op.get_bind().dialect.name == "postgresql":
        for name in (
            "ix_commitments_search_gin",
            "ix_users_lower_email",
            "ix_users_lower_name",
        ):
            op.execute("DROP INDEX " + name)
    op.drop_table("login_throttles")
    for table, name in [
        ("source_inbox", "ix_source_inbox_thread_id"),
        ("source_inbox", "ix_source_recipient_thread"),
        ("source_inbox", "ix_source_lease"),
        ("commitments", "ix_commitments_org_due_id"),
        ("login_sessions", "ix_sessions_expiry"),
    ]:
        op.drop_index(name, table_name=table)
    for col in ("thread_id", "claim_token", "claimed_until"):
        op.drop_column("source_inbox", col)
    for col in ("password_hash", "timezone"):
        op.drop_column("users", col)
