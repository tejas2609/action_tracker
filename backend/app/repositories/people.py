from sqlalchemy import select, delete
from app.models.people import User, LoginSession


class PeopleRepository:
    def __init__(self, db):
        self.db = db

    def active_users(self, organization_id=None):
        query = select(User).where(User.active.is_(True))
        if organization_id is not None:
            query = query.where(User.organization_id == organization_id)
        return list(self.db.scalars(query.order_by(User.name)))

    def revoke_session(self, token_hash):
        self.db.execute(
            delete(LoginSession).where(LoginSession.token_hash == token_hash)
        )

    def messages(self, conversation_id, before=None, limit=50):
        from sqlalchemy import or_, and_
        from app.models.people import Message

        query = select(Message).where(Message.conversation_id == conversation_id)
        if before is not None:
            query = query.where(
                or_(
                    Message.created_at < before.created_at,
                    and_(
                        Message.created_at == before.created_at, Message.id < before.id
                    ),
                )
            )
        return list(
            self.db.scalars(
                query.order_by(Message.created_at.desc(), Message.id.desc()).limit(
                    limit + 1
                )
            )
        )
