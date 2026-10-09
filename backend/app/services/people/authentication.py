"""Authentication service; no public registration or shared production passwords."""

import hashlib, secrets, time
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, delete, func
from app.core.config import settings
from app.core.security import verify_password, hash_password
from app.models.people import User, LoginSession
from app.models.security import LoginThrottle

# Equal-cost password verification for unknown users.
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class AuthenticationService:
    def __init__(self, db):
        self.db = db

    def throttle(self, username, request):
        # Direct peer address only; forwarded headers require a trusted proxy config.
        peer = request.client.host if request and request.client else "unknown"
        bucket = int(time.time()) // 60
        dialect = self.db.bind.dialect.name
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        # Limit by IP AND identity. Rotation of one alone cannot bypass both limits.
        for value in ("ip:" + peer, "account:" + username):
            key = hashlib.sha256(value.encode()).hexdigest()
            statement = insert(LoginThrottle).values(key=key, bucket=bucket, attempts=1)
            statement = statement.on_conflict_do_update(
                index_elements=[LoginThrottle.key, LoginThrottle.bucket],
                set_={"attempts": LoginThrottle.attempts + 1},
            ).returning(LoginThrottle.attempts)
            count = self.db.scalar(statement)
            if count > settings.login_attempts_per_minute:
                self.db.commit()
                raise HTTPException(
                    429, "Too many login attempts", headers={"Retry-After": "60"}
                )
        self.db.execute(delete(LoginThrottle).where(LoginThrottle.bucket < bucket - 2))
        self.db.commit()

    def login(self, body, request=None):
        from app.services.people.social import public_user

        username = body.username.strip().lower()
        self.throttle(username, request)
        users = list(
            self.db.scalars(
                select(User)
                .where(
                    User.active.is_(True),
                    (func.lower(User.email) == username)
                    | (func.lower(User.name) == username),
                )
                .limit(2)
            )
        )
        user = users[0] if len(users) == 1 else None
        encoded = user.password_hash if user and user.password_hash else DUMMY_HASH
        valid = verify_password(body.password, encoded)
        if (
            settings.demo_login_enabled
            and settings.environment == "development"
            and user
            and not user.password_hash
        ):
            valid = secrets.compare_digest(body.password, "pass")
        if not user or not valid:
            raise HTTPException(401, "Invalid username or password")
        if request:
            request.state.user_id, request.state.organization_id = (
                user.id,
                user.organization_id,
            )
        token = secrets.token_urlsafe(32)
        self.db.execute(
            delete(LoginSession).where(
                LoginSession.expires_at < datetime.now(timezone.utc)
            )
        )
        self.db.add(
            LoginSession(
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user.id,
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=settings.session_hours),
            )
        )
        self.db.commit()
        return {"token": token, "user": public_user(user)}
