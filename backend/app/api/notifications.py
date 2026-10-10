import asyncio
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.auth import current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import now
from app.models.notifications import Notification
from app.models.people import User
from app.services.notifications.notification_hub import hub
from app.services.notifications.notifications import (
    authenticate_socket,
    notification_snapshot,
    saved_notifications,
)

router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"],
)


@router.get("")
def list_notifications(
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return saved_notifications(db, actor.organization_id, actor.id)


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    scope = (
        Notification.organization_id == actor.organization_id,
        Notification.recipient_id == actor.id,
        Notification.id == notification_id,
    )

    exists = db.scalar(select(Notification.id).where(*scope))

    if not exists:
        raise HTTPException(404, "Notification not found")

    db.execute(
        update(Notification)
        .where(*scope, Notification.read_at.is_(None))
        .values(read_at=now())
    )
    db.commit()

    return {"ok": True}


@router.websocket("/ws")
async def notifications_socket(socket: WebSocket):
    allowed_origins = {value.strip() for value in settings.cors_origins.split(",")}

    if socket.headers.get("origin") not in allowed_origins:
        await socket.close(code=1008)
        return

    await socket.accept()

    subscription = None
    tasks = []

    try:
        # Browser WebSockets cannot use your HTTP bearer interceptor.
        # Authenticate in the first frame, not in the URL.
        message = await asyncio.wait_for(
            socket.receive_json(),
            timeout=10,
        )

        if not isinstance(message, dict):
            await socket.close(code=1008)
            return

        token = message.get("token")

        if (
            message.get("type") != "auth"
            or not isinstance(token, str)
            or not 1 <= len(token) <= 4096
        ):
            await socket.close(code=1008)
            return

        identity = await run_in_threadpool(authenticate_socket, token)

        if not identity:
            await socket.close(code=1008)
            return

        organization_id, recipient_id, expiry = identity

        key, queue = hub.subscribe(organization_id, recipient_id)
        subscription = (key, queue)

        # Initial saved state, also recovering anything missed offline.
        queue.put_nowait(True)

        async def send_snapshots():
            while True:
                await queue.get()

                # Validate session/account before sending each snapshot.
                current = await run_in_threadpool(authenticate_socket, token)

                if not current or current[:2] != identity[:2]:
                    await socket.close(code=1008)
                    return

                snapshot = await run_in_threadpool(
                    notification_snapshot,
                    organization_id,
                    recipient_id,
                )

                await asyncio.wait_for(
                    socket.send_json(snapshot),
                    timeout=10,
                )

        async def receive_disconnect():
            while True:
                await socket.receive_text()

        async def expire_session():
            remaining = (expiry - datetime.now(timezone.utc)).total_seconds()

            await asyncio.sleep(max(0, remaining))
            await socket.close(code=1008)

        tasks = [
            asyncio.create_task(send_snapshots()),
            asyncio.create_task(receive_disconnect()),
            asyncio.create_task(expire_session()),
        ]

        done, _ = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            task.result()

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await socket.close(code=1011)
        except RuntimeError:
            pass
    finally:
        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if subscription:
            hub.unsubscribe(*subscription)
