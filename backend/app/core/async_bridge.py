"""Execute legacy sync-DB async use cases off the ASGI event loop.
A Session is used sequentially, never concurrently. New queue processing uses
explicit isolated database stages instead of this compatibility boundary.
"""

import asyncio
from starlette.concurrency import run_in_threadpool


async def run_legacy(operation, *args, **kwargs):
    return await run_in_threadpool(lambda: asyncio.run(operation(*args, **kwargs)))
