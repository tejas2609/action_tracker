import asyncio, logging
from starlette.concurrency import run_in_threadpool
from app.ai.provider import get_provider
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.services.sources.source_actions import claim_next, execute_claim


def claim():
    with SessionLocal() as db:
        return claim_next(db)


async def consumer():
    while True:
        try:
            job = await run_in_threadpool(claim)
            if job:
                await run_in_threadpool(
                    lambda: asyncio.run(
                        execute_claim(SessionLocal, job, get_provider())
                    )
                )
            else:
                await asyncio.sleep(2)
        except Exception as error:
            logging.warning("Source consumer error: %s", type(error).__name__)
            await asyncio.sleep(2)


async def main():
    from app.main import validate_configuration

    validate_configuration()
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Workers require PostgreSQL")
    try:
        async with asyncio.TaskGroup() as group:
            for _ in range(settings.worker_concurrency):
                group.create_task(consumer())
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(main())
