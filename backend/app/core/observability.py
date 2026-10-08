import logging
from time import perf_counter
from uuid import uuid4
from starlette.concurrency import run_in_threadpool
from app.core.database import SessionLocal
from app.models.logs import AuthLog, GeneralLog, ErrorLog

logger = logging.getLogger(__name__)


def persist(records):
    try:
        with SessionLocal() as db:
            db.add_all(records)
            db.commit()
    except Exception as error:
        # Logging failure must not replace the application's original response.
        logger.error("Database log write failed: %s", type(error).__name__)


async def request_log(request, call_next):
    started = perf_counter()
    identifier = str(uuid4())
    error_type = None
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = identifier
        return response
    except Exception as error:
        error_type = type(error).__name__
        raise
    finally:
        route = request.scope.get("route")
        # Template path excludes OAuth codes, IDs and query strings.
        action = request.method + " " + getattr(route, "path", "/unmatched")
        values = dict(
            action=action,
            request_id=identifier,
            user_id=getattr(request.state, "user_id", None),
            organization_id=getattr(request.state, "organization_id", None),
            status_code=status,
            duration_ms=(perf_counter() - started) * 1000,
        )
        records = []
        if "/auth/" in action or status == 401:
            records.append(AuthLog(**values))
        elif request.method != "GET":
            records.append(GeneralLog(**values))
        if status >= 400:
            records.append(
                ErrorLog(**values, error_type=error_type or ("http_" + str(status)))
            )
        if records:
            await run_in_threadpool(persist, records)
        logger.info(
            "%s status=%s duration_ms=%.2f request_id=%s",
            action,
            status,
            values["duration_ms"],
            identifier,
        )
