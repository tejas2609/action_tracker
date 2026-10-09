"""Persistent unread status for direct messages."""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "messages",
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Treat messages from before this feature as already read.
    # Messages sent after the migration default to unread.
    op.execute("UPDATE messages SET read_at = created_at")

    op.create_index(
        "ix_messages_unread",
        "messages",
        ["conversation_id", "sender_id", "created_at", "id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )


def downgrade():
    op.drop_index("ix_messages_unread", table_name="messages")
    op.drop_column("messages", "read_at")
