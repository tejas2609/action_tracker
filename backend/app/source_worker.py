import asyncio
import logging

from app.ai.provider import get_provider
from app.core.database import SessionLocal
from app.services.source_actions import process_next


async def main():
    ai = get_provider()
    logger = logging.getLogger(__name__)

    try:
        while True:
            try:
                with SessionLocal() as db:
                    async with asyncio.timeout(90):
                        worked = await process_next(db, ai)

            except Exception as error:
                logger.warning(
                    "Source worker failed: %s",
                    type(error).__name__,
                )
                worked = False

            await asyncio.sleep(0.1 if worked else 2)

    finally:
        await ai.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
