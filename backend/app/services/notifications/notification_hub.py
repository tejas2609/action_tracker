import asyncio
import json
import logging
from collections import defaultdict

import psycopg

from app.core.database import engine

log = logging.getLogger(__name__)


class NotificationHub:
    def __init__(self):
        self.clients = defaultdict(set)
        self.ready = asyncio.Event()
        self.task = None

    def subscribe(self, organization_id, recipient_id):
        # Coalesce bursts: one pending snapshot refresh is enough.
        queue = asyncio.Queue(maxsize=1)
        key = (organization_id, recipient_id)
        self.clients[key].add(queue)
        return key, queue

    def unsubscribe(self, key, queue):
        queues = self.clients.get(key)

        if not queues:
            return

        queues.discard(queue)

        if not queues:
            self.clients.pop(key, None)

    def publish(self, key):
        for queue in tuple(self.clients.get(key, ())):
            if queue.empty():
                queue.put_nowait(True)

    def resync_all(self):
        for key in tuple(self.clients):
            self.publish(key)

    async def start(self):
        self.ready.clear()
        self.task = asyncio.create_task(self.listen())

        try:
            await asyncio.wait_for(self.ready.wait(), timeout=15)
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        if self.task:
            self.task.cancel()

            try:
                await self.task
            except asyncio.CancelledError:
                pass

            self.task = None

    async def listen(self):
        args, kwargs = engine.dialect.create_connect_args(engine.url)
        kwargs = dict(kwargs)
        kwargs["autocommit"] = True

        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    *args, **kwargs
                ) as connection:
                    await connection.execute("LISTEN tracker_notifications")

                    self.ready.set()

                    # Refresh connected clients after listener reconnection.
                    self.resync_all()

                    async for event in connection.notifies():
                        payload = json.loads(event.payload)

                        self.publish(
                            (
                                payload["organization_id"],
                                payload["recipient_id"],
                            )
                        )

            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Notification listener disconnected")
                await asyncio.sleep(2)


hub = NotificationHub()
