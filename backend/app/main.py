import logging
from contextlib import asynccontextmanager
from app.core.observability import request_log
from app.ai.provider import get_provider
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.models import security as security_models  # noqa: F401 - register ORM table
from app.api.routes import router
from app.api.social import router as social_router
from app.api.profile import router as profile_router
from app.api.meeting_deletion import router as deletion_router
from app.api.integrations import router as integrations_router
from app.api.email_actions import router as email_actions_router
from app.features.meeting_agendas.routes import router as meeting_agendas_router
from app.api.meeting_access import router as meeting_access_router
from app.api.source_actions import router as source_actions_router


@asynccontextmanager
async def lifespan(app):
    logging.basicConfig(level=settings.log_level)
    validate_configuration()
    try:
        yield
    finally:
        try:
            if get_provider.cache_info().currsize:
                await get_provider().close()
                get_provider.cache_clear()
        finally:
            engine.dispose()


from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.http_security import SecurityMiddleware
from app.core.security import data_cipher
from app.core.database import engine


def validate_configuration():
    data_cipher()  # fail fast on invalid encryption keys
    if settings.worker_lease_seconds < 300 or settings.worker_concurrency < 1:
        raise RuntimeError(
            "Worker lease must be >=300 seconds; concurrency must be positive"
        )
    if settings.environment == "production":
        if settings.demo_login_enabled:
            raise RuntimeError("Demo login must be disabled in production")
        if not settings.data_encryption_keys:
            raise RuntimeError("Production requires DATA_ENCRYPTION_KEYS")
        if "*" in settings.allowed_hosts or "*" in settings.cors_origins:
            raise RuntimeError("Production requires explicit hosts and CORS origins")
        if not settings.frontend_url.startswith("https://"):
            raise RuntimeError("Production frontend requires HTTPS")
        if settings.google_client_id and not settings.oauth_cookie_secure:
            raise RuntimeError("Production OAuth cookies must be secure")


app = FastAPI(
    title="Action Tracker",
    version="2.1.0",
    lifespan=lifespan,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts.split(",")
)
app.add_middleware(SecurityMiddleware)
from app.core.errors import validation_error
from fastapi.exceptions import RequestValidationError

app.add_exception_handler(RequestValidationError, validation_error)
app.middleware("http")(request_log)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(social_router)
app.include_router(deletion_router)
app.include_router(profile_router)
app.include_router(integrations_router)
app.include_router(email_actions_router)
app.include_router(meeting_agendas_router)
app.include_router(meeting_access_router)
app.include_router(source_actions_router)
