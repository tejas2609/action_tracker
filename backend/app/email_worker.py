"""Gmail discovery worker; run source_worker as well for extraction."""

import asyncio, logging
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from app.ai.provider import get_provider
from app.core.database import SessionLocal, engine
from app.core.config import settings
from app.models.integrations import GmailConnection
from app.models.people import User
from app.services.email.email_actions import scan


def user_ids():
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(User.id)
                .join(GmailConnection, GmailConnection.user_id == User.id)
                .where(User.active.is_(True))
            )
        )


def scan_user(user_id):
    with SessionLocal() as db:
        actor = db.get(User, user_id)
        if actor and actor.active:
            return asyncio.run(scan(db, actor, get_provider()))


async def main():
    from app.main import validate_configuration

    validate_configuration()
    semaphore = asyncio.Semaphore(settings.worker_concurrency)

    async def account(user_id):
        async with semaphore:
            try:
                await run_in_threadpool(scan_user, user_id)
            except Exception as error:
                logging.warning("Gmail ingestion failed: %s", type(error).__name__)

    try:
        while True:
            ids = await run_in_threadpool(user_ids)
            await asyncio.gather(*(account(identifier) for identifier in ids))
            await asyncio.sleep(30)
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(main())
