import asyncio
import logging

from sqlalchemy import select

from app.ai.provider import get_provider
from app.core.database import SessionLocal
from app.models.integrations import GmailConnection
from app.models.people import User
from app.services.email_actions import scan

logger = logging.getLogger(__name__)


async def main():
    ai = get_provider()

    while True:
        with SessionLocal() as db:
            user_ids = list(
                db.scalars(
                    select(User.id)
                    .join(
                        GmailConnection,
                        GmailConnection.user_id == User.id,
                    )
                    .where(User.active.is_(True))
                )
            )

        for user_id in user_ids:
            with SessionLocal() as db:
                actor = db.get(User, user_id)

                if not actor or not actor.active:
                    continue

                try:
                    await scan(db, actor, ai)

                except Exception as error:
                    db.rollback()

                    # Log error type only, never email content or tokens.
                    logger.warning(
                        "Gmail scan failed: user_id=%s error_type=%s",
                        user_id,
                        type(error).__name__,
                    )

        await asyncio.sleep(30)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
