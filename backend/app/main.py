import logging
from contextlib import asynccontextmanager
from app.core.observability import request_log
from app.ai.provider import get_provider
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import router
from app.api.social import router as social_router
from app.api.profile import router as profile_router
from app.api.meeting_deletion import router as deletion_router
from app.api.integrations import router as integrations_router
from app.api.email_actions import router as email_actions_router
from app.features.meeting_agendas.routes import router as meeting_agendas_router
from app.api.meeting_access import router as meeting_access_router


@asynccontextmanager
async def lifespan(app):
    logging.basicConfig(level=settings.log_level)
    yield
    if get_provider.cache_info().currsize:
        await get_provider().close()
        get_provider.cache_clear()


app = FastAPI(title="Action Tracker", version="2.0.0", lifespan=lifespan)
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
