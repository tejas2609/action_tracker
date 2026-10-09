from alembic import op
import sqlalchemy as sa

revision = "009_source_actions"
down_revision = "008_commitment_created_at"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_inbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recipient_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "state",
            sa.String(20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_error",
            sa.String(120),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "source",
            "external_id",
            "recipient_id",
            name="uq_source_recipient_message",
        ),
    )

    op.create_index(
        "ix_source_inbox_pending",
        "source_inbox",
        ["state", "available_at", "created_at"],
    )

    op.create_table(
        "commitment_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "inbox_id",
            sa.String(36),
            sa.ForeignKey("source_inbox.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "commitment_id",
            sa.String(36),
            sa.ForeignKey("commitments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "inbox_id",
            "commitment_id",
            name="uq_source_commitment",
        ),
    )

    op.create_index(
        "ix_commitment_sources_commitment",
        "commitment_sources",
        ["commitment_id"],
    )


def downgrade():
    op.drop_table("commitment_sources")
    op.drop_table("source_inbox")
