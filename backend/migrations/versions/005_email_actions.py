"""Support email commitments and selective email retention."""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def user_fk():
    return sa.ForeignKey("users.id", ondelete="CASCADE")


def commitment_fk():
    return sa.ForeignKey("commitments.id", ondelete="CASCADE")


def upgrade():
    op.add_column(
        "commitments",
        sa.Column("organization_id", sa.String(36), nullable=True),
    )

    op.execute("""
        UPDATE commitments AS c
        SET organization_id = m.organization_id
        FROM meetings AS m
        WHERE c.meeting_id = m.id
    """)

    op.alter_column(
        "commitments",
        "organization_id",
        nullable=False,
    )

    op.create_foreign_key(
        "fk_commitments_organization",
        "commitments",
        "organizations",
        ["organization_id"],
        ["id"],
    )

    op.create_index(
        "ix_commitments_organization_id",
        "commitments",
        ["organization_id"],
    )

    op.alter_column("commitments", "meeting_id", nullable=True)

    op.create_table(
        "email_sync_states",
        sa.Column("user_id", sa.String(36), user_fk(), primary_key=True),
        sa.Column("google_sub", sa.String(255), nullable=False),
        sa.Column("history_id", sa.String(100), nullable=False),
        sa.Column("history_page", sa.Text(), nullable=True),
        sa.Column("bootstrap_done", sa.Boolean(), nullable=False),
        sa.Column("bootstrap_after", sa.BigInteger(), nullable=False),
        sa.Column("bootstrap_before", sa.BigInteger(), nullable=False),
        sa.Column("bootstrap_page", sa.Text(), nullable=True),
        sa.Column(
            "last_history_sync",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_table(
        "email_processing",
        sa.Column("user_id", sa.String(36), user_fk(), primary_key=True),
        sa.Column("google_sub", sa.String(255), primary_key=True),
        sa.Column("message_id", sa.String(255), primary_key=True),
        sa.Column("state", sa.String(30), nullable=False),
    )

    op.create_index(
        "ix_email_processing_state",
        "email_processing",
        ["state"],
    )

    op.create_table(
        "email_origins",
        sa.Column(
            "commitment_id",
            sa.String(36),
            commitment_fk(),
            primary_key=True,
        ),
        sa.Column("user_id", sa.String(36), user_fk(), nullable=False),
        sa.Column("google_sub", sa.String(255), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(1000), nullable=False),
        sa.Column("sender", sa.String(1000), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
    )

    op.create_table(
        "commitment_emails",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "commitment_id",
            sa.String(36),
            commitment_fk(),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(36), user_fk(), nullable=False),
        sa.Column("google_sub", sa.String(255), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(1000), nullable=False),
        sa.Column("sender", sa.String(1000), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "commitment_id",
            "user_id",
            "google_sub",
            "message_id",
            name="uq_commitment_email",
        ),
    )

    op.create_index(
        "ix_commitment_emails_commitment_id",
        "commitment_emails",
        ["commitment_id"],
    )

    op.create_index(
        "ix_commitment_emails_user_id",
        "commitment_emails",
        ["user_id"],
    )


def downgrade():
    # Email commitments must be removed or assigned real meetings first.
    connection = op.get_bind()

    count = connection.execute(
        sa.text("SELECT count(*) FROM commitments WHERE meeting_id IS NULL")
    ).scalar_one()

    if count:
        raise RuntimeError("Cannot downgrade while commitments without meetings exist.")

    op.drop_table("commitment_emails")
    op.drop_table("email_origins")
    op.drop_table("email_processing")
    op.drop_table("email_sync_states")

    op.alter_column("commitments", "meeting_id", nullable=False)

    op.drop_index(
        "ix_commitments_organization_id",
        table_name="commitments",
    )

    op.drop_constraint(
        "fk_commitments_organization",
        "commitments",
        type_="foreignkey",
    )

    op.drop_column("commitments", "organization_id")
