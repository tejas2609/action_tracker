"""Add reporting relationships and Nina's initial team."""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

ORG = "00000000-0000-0000-0000-000000000001"


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "is_manager",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("manager_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_users_manager",
            "users",
            ["manager_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_users_manager_id",
            ["manager_id"],
        )

    db = op.get_bind()

    nina_id = db.execute(
        sa.text("""
            SELECT id
            FROM users
            WHERE organization_id = :org
              AND lower(trim(name)) = 'nina'
        """),
        {"org": ORG},
    ).scalar_one_or_none()

    if nina_id is not None:
        db.execute(
            sa.text("""
                UPDATE users
                SET is_manager = true
                WHERE id = :id
            """),
            {"id": nina_id},
        )

        db.execute(
            sa.text("""
                UPDATE users
                SET manager_id = :manager
                WHERE organization_id = :org
                  AND manager_id IS NULL
                  AND lower(trim(name)) IN (
                      'alex', 'daniel', 'leo', 'maya'
                  )
            """),
            {"manager": nina_id, "org": ORG},
        )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_manager_id")
        batch.drop_constraint(
            "fk_users_manager",
            type_="foreignkey",
        )
        batch.drop_column("manager_id")
        batch.drop_column("is_manager")
