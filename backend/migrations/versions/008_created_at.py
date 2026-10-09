"""Add creation timestamp to commitments."""

from alembic import op
import sqlalchemy as sa

revision = "008_commitment_created_at"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "commitments",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_column("commitments", "created_at")
