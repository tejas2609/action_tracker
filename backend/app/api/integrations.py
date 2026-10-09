from app.core.async_bridge import run_legacy
import logging

import httpx

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import current_user, security
from app.core.config import settings
from app.core.database import get_db
from app.models.people import User
from app.services.email import gmail_integration as gmail

router = APIRouter(
    prefix="/api/integrations/gmail",
    tags=["integrations"],
)

logger = logging.getLogger(__name__)


@router.get("")
def get_status(
    response: Response,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    return gmail.status(db, actor)


@router.post("/connect")
def connect(
    response: Response,
    actor: User = Depends(current_user),
    credentials=Depends(security),
    db: Session = Depends(get_db),
):
    authorization_url, browser = gmail.begin(
        db,
        actor,
        credentials.credentials,
    )

    response.set_cookie(
        key=gmail.COOKIE_NAME,
        value=browser,
        max_age=600,
        httponly=True,
        secure=settings.oauth_cookie_secure,
        samesite="lax",
        path=gmail.COOKIE_PATH,
    )

    response.headers["Cache-Control"] = "no-store"

    return {
        "authorization_url": authorization_url,
    }


@router.get("/callback")
async def callback(
    request: Request,
    state: str = "",
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        result = await run_legacy(
            gmail.complete,
            db,
            state,
            request.cookies.get(gmail.COOKIE_NAME, ""),
            code,
            error,
        )

    except HTTPException:
        db.rollback()
        result = "failed"

    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        InvalidToken,
    ):
        db.rollback()

        # Do not log codes, tokens, callback URLs, or Google responses.
        logger.warning("Gmail OAuth callback failed")

        result = "failed"

    response = RedirectResponse(
        url=(settings.frontend_url.rstrip("/") + "/integrations?gmail=" + result),
        status_code=303,
    )

    response.delete_cookie(
        key=gmail.COOKIE_NAME,
        path=gmail.COOKIE_PATH,
        secure=settings.oauth_cookie_secure,
        httponly=True,
        samesite="lax",
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"

    return response


@router.delete("")
async def remove(
    response: Response,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"

    try:
        return await run_legacy(gmail.disconnect, db, actor)

    except httpx.HTTPError:
        raise HTTPException(
            502,
            "Cannot reach Google. Retry disconnecting.",
        ) from None

    except InvalidToken:
        raise HTTPException(
            503,
            "Stored credentials cannot be decrypted. Check INTEGRATION_TOKEN_KEY.",
        ) from None
