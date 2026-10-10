"""Persistent notifications and committed event delivery."""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
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
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(600), nullable=False),
        sa.Column("event_key", sa.String(150), nullable=False),
        sa.Column("peer_id", sa.String(36), nullable=True),
        sa.Column("commitment_id", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "recipient_id",
            "event_key",
            name="uq_notifications_recipient_event",
        ),
    )

    op.create_index(
        "ix_notifications_recipient_created",
        "notifications",
        ["recipient_id", "created_at", "id"],
    )
    op.create_index(
        "ix_notifications_recipient_read",
        "notifications",
        ["recipient_id", "read_at"],
    )

    op.execute("""
        CREATE FUNCTION publish_notification_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            PERFORM pg_notify(
                'tracker_notifications',
                json_build_object(
                    'organization_id', NEW.organization_id,
                    'recipient_id', NEW.recipient_id
                )::text
            );
            RETURN NEW;
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER notification_event_trigger
        AFTER INSERT OR UPDATE OF read_at
        ON notifications
        FOR EACH ROW
        EXECUTE FUNCTION publish_notification_event();
    """)


def downgrade():
    op.execute("""
        DROP TRIGGER notification_event_trigger ON notifications;
    """)
    op.execute("""
        DROP FUNCTION publish_notification_event();
    """)

    op.drop_index(
        "ix_notifications_recipient_read",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_recipient_created",
        table_name="notifications",
    )
    op.drop_table("notifications")
