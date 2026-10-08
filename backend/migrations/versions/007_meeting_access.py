from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    # Existing meetings default to private until their participants
    # are explicitly recorded. New meetings use the form selection.
    op.add_column(
        "meetings",
        sa.Column(
            "visibility",
            sa.String(10),
            nullable=False,
            server_default="private",
        ),
    )

    op.create_index(
        "ix_meetings_visibility",
        "meetings",
        ["visibility"],
    )

    op.create_table(
        "meeting_participants",
        sa.Column(
            "meeting_id",
            sa.String(36),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_index(
        "ix_meeting_participants_user_id",
        "meeting_participants",
        ["user_id"],
    )

    op.create_table(
        "meeting_access_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(36),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requester_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "decided_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "meeting_id",
            "requester_id",
            name="uq_meeting_access_request",
        ),
    )

    for name, columns in (
        ("ix_meeting_access_requests_meeting_id", ["meeting_id"]),
        ("ix_meeting_access_requests_requester_id", ["requester_id"]),
        ("ix_meeting_access_requests_status", ["status"]),
    ):
        op.create_index(name, "meeting_access_requests", columns)


def downgrade():
    op.drop_table("meeting_access_requests")
    op.drop_table("meeting_participants")
    op.drop_index("ix_meetings_visibility", table_name="meetings")
    op.drop_column("meetings", "visibility")
