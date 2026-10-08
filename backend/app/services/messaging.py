"""Membership and direct-conversation orchestration, independent of transport."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.people import User, Conversation


def peer_user(db, actor, id):
    u = db.get(User, id)
    if not u or not u.active or u.organization_id != actor.organization_id:
        raise HTTPException(404, "Organization user not found")
    if u.id == actor.id:
        raise HTTPException(422, "Choose another user to message.")
    return u


def conversation(db, actor, peer):
    a, b = sorted([actor.id, peer.id])
    q = select(Conversation).where(
        Conversation.organization_id == actor.organization_id,
        Conversation.user_a_id == a,
        Conversation.user_b_id == b,
    )
    c = db.scalar(q)
    if c:
        return c
    try:
        with db.begin_nested():
            c = Conversation(
                organization_id=actor.organization_id, user_a_id=a, user_b_id=b
            )
            db.add(c)
            db.flush()
    except IntegrityError:
        c = db.scalar(q)
    return c
