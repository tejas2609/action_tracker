"""Add Gmail integration tables."""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gmail_connections",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("google_sub", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_table(
        "gmail_oauth_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_hash", sa.String(64), nullable=False),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("verifier_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_gmail_oauth_states_user_id",
        "gmail_oauth_states",
        ["user_id"],
    )

    op.create_index(
        "ix_gmail_oauth_states_expires_at",
        "gmail_oauth_states",
        ["expires_at"],
    )


def downgrade():
    op.drop_table("gmail_oauth_states")
    op.drop_table("gmail_connections")
