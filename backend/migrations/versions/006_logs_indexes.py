"""Operational logs and targeted lookup indexes."""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_events_commitment_created", "events", ["commitment_id", "created_at"]),
    ("ix_dependencies_prerequisite", "dependencies", ["prerequisite_id"]),
    (
        "ix_commitments_org_owner_status",
        "commitments",
        ["organization_id", "owner_id", "status"],
    ),
    (
        "ix_messages_conversation_created_id",
        "messages",
        ["conversation_id", "created_at", "id"],
    ),
]


def upgrade():
    for table in ("auth_logs", "general_logs", "error_logs"):
        columns = [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("action", sa.String(200), nullable=False),
            sa.Column("request_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36)),
            sa.Column("organization_id", sa.String(36)),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("duration_ms", sa.Float(), nullable=False),
        ]
        if table == "error_logs":
            columns.append(sa.Column("error_type", sa.String(100), nullable=False))
        op.create_table(table, *columns)
        op.create_index("ix_" + table + "_timestamp", table, ["timestamp"])
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
    for table in ("error_logs", "general_logs", "auth_logs"):
        op.drop_index("ix_" + table + "_timestamp", table_name=table)
        op.drop_table(table)
