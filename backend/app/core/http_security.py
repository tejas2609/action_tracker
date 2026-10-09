"""ASGI body limits, host checks (main), and response privacy headers."""

from starlette.responses import JSONResponse
from app.core.config import settings


class BodyTooLarge(Exception):
    pass


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid content length"}, 400)(
                scope, receive, send
            )
        if length > settings.max_request_bytes:
            return await JSONResponse({"detail": "Request body too large"}, 413)(
                scope, receive, send
            )
        size, exceeded = 0, False

        async def bounded_receive():
            nonlocal size, exceeded
            message = await receive()
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > settings.max_request_bytes:
                    exceeded = True
                    raise BodyTooLarge()
            return message

        async def secured_send(message):
            if message["type"] == "http.response.start":
                if exceeded:
                    message = {**message, "status": 413}
                values = list(message.get("headers", []))
                values += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                ]
                if settings.environment == "production":
                    values.append(
                        (
                            b"strict-transport-security",
                            b"max-age=31536000; includeSubDomains",
                        )
                    )
                message["headers"] = values
            if exceeded and message["type"] == "http.response.body":
                message = {
                    "type": "http.response.body",
                    "body": b'{"detail":"Request body too large"}',
                }
            await send(message)

        try:
            await self.app(scope, bounded_receive, secured_send)
        except BodyTooLarge:
            await JSONResponse({"detail": "Request body too large"}, 413)(
                scope, receive, send
            )
