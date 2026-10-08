from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.people import User, Organization
from app.models.entities import Commitment
from app.services.social import public_user


def profile_data(db: Session, actor: User):
    manager = db.get(User, actor.manager_id) if actor.manager_id else None

    members = []
    available = []

    if actor.is_manager:
        members = list(
            db.scalars(
                select(User)
                .where(
                    User.organization_id == actor.organization_id,
                    User.manager_id == actor.id,
                    User.active == True,
                )
                .order_by(User.name, User.id)
            )
        )

        # Exclude the manager and their ancestors:
        # assigning an ancestor would create a reporting cycle.
        excluded = {actor.id}
        cursor = actor.manager_id

        while cursor and cursor not in excluded:
            excluded.add(cursor)
            ancestor = db.get(User, cursor)
            cursor = ancestor.manager_id if ancestor else None

        available = list(
            db.scalars(
                select(User)
                .where(
                    User.organization_id == actor.organization_id,
                    User.active == True,
                    User.manager_id.is_(None),
                    User.id.notin_(excluded),
                )
                .order_by(User.name, User.id)
            )
        )

    return {
        "user": public_user(actor),
        "manager": public_user(manager) if manager else None,
        "members": [public_user(u) for u in members],
        "available": [public_user(u) for u in available],
    }


def lock_organization(db: Session, actor: User):
    # Serialize reporting changes within this organization.
    # PostgreSQL holds the lock until commit or rollback.
    db.execute(
        select(Organization)
        .where(Organization.id == actor.organization_id)
        .with_for_update()
    ).scalar_one()

    db.refresh(actor)


def require_manager(actor: User):
    if not actor.is_manager:
        raise HTTPException(
            403,
            "Only managers can change team membership.",
        )


def get_profile(actor=None, db=None):
    return profile_data(db, actor)


def update_profile(body, actor=None, db=None):
    name = body.name.strip()
    email = body.email.strip().lower()
    if not name or not email:
        raise HTTPException(422, "Name and email are required.")
    lock_organization(db, actor)
    duplicate_name = db.scalar(
        select(User.id).where(
            User.id != actor.id, func.lower(func.trim(User.name)) == name.lower()
        )
    )
    if duplicate_name:
        raise HTTPException(409, "This name is already used as a username.")
    duplicate_email = db.scalar(
        select(User.id).where(User.id != actor.id, func.lower(User.email) == email)
    )
    if duplicate_email:
        raise HTTPException(409, "This email is already in use.")
    actor.name = name
    actor.email = email
    db.execute(
        update(Commitment).where(Commitment.owner_id == actor.id).values(owner=name)
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Profile details conflict with another user.")
    return profile_data(db, actor)


def add_member(user_id, actor=None, db=None):
    lock_organization(db, actor)
    require_manager(actor)
    if user_id == actor.id:
        raise HTTPException(422, "You cannot manage yourself.")
    target = db.scalar(
        select(User).where(
            User.id == user_id,
            User.organization_id == actor.organization_id,
            User.active == True,
        )
    )
    if not target:
        raise HTTPException(404, "User not found.")
    if target.manager_id is not None:
        raise HTTPException(409, "This user already has a manager.")
    cursor = actor.id
    visited = set()
    while cursor:
        if cursor == target.id:
            raise HTTPException(422, "This assignment would create a reporting cycle.")
        if cursor in visited:
            raise HTTPException(409, "The reporting hierarchy needs correction.")
        visited.add(cursor)
        person = db.get(User, cursor)
        cursor = person.manager_id if person else None
    result = db.execute(
        update(User)
        .where(
            User.id == target.id,
            User.organization_id == actor.organization_id,
            User.manager_id.is_(None),
        )
        .values(manager_id=actor.id)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "This user was assigned to another manager.")
    db.commit()
    return profile_data(db, actor)


def remove_member(user_id, actor=None, db=None):
    lock_organization(db, actor)
    require_manager(actor)
    result = db.execute(
        update(User)
        .where(
            User.id == user_id,
            User.organization_id == actor.organization_id,
            User.manager_id == actor.id,
        )
        .values(manager_id=None)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(404, "This user is not in your team.")
    db.commit()
    return profile_data(db, actor)
