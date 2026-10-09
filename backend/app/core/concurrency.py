from sqlalchemy import select
from app.models.people import Organization


def lock_organization(db, organization_id):
    """Acquire before graph read/check/write; PostgreSQL serializes mutations."""
    db.scalar(
        select(Organization).where(Organization.id == organization_id).with_for_update()
    )
