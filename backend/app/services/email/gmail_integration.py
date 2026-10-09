import base64
import hashlib
import secrets

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

import httpx

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.integrations import GmailConnection, GmailOAuthState
from app.models.people import LoginSession, User

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

SCOPES = [
    "openid",
    "email",
    "profile",
    GMAIL_SCOPE,
]

COOKIE_NAME = "tracker_gmail_oauth"
COOKIE_PATH = "/api/integrations/gmail/callback"


def now():
    return datetime.now(timezone.utc)


def aware(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def cipher():
    try:
        return Fernet(settings.integration_token_key.encode())

    except (ValueError, TypeError):
        raise HTTPException(
            503,
            "Configure INTEGRATION_TOKEN_KEY with a valid Fernet key.",
        ) from None


def configured():
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.integration_token_key
    )


def require_configuration():
    if not configured():
        raise HTTPException(
            503,
            "Gmail integration has not been configured.",
        )

    cipher()

    for value in (
        settings.google_redirect_uri,
        settings.frontend_url,
    ):
        parsed = urlsplit(value)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(
                503,
                "Invalid integration URL configuration.",
            )

        if parsed.scheme == "http" and parsed.hostname not in (
            "localhost",
            "127.0.0.1",
        ):
            raise HTTPException(
                503,
                "Use HTTPS for deployed integration URLs.",
            )

    redirect = urlsplit(settings.google_redirect_uri)

    if redirect.path != COOKIE_PATH:
        raise HTTPException(
            503,
            "GOOGLE_REDIRECT_URI must end with " + COOKIE_PATH,
        )

    if redirect.scheme == "https" and not settings.oauth_cookie_secure:
        raise HTTPException(
            503,
            "Enable OAUTH_COOKIE_SECURE for HTTPS.",
        )


def status(db: Session, actor: User):
    connection = db.get(GmailConnection, actor.id)

    return {
        "configured": configured(),
        "connected": connection is not None,
        "account": (
            {
                "email": connection.email,
                "name": connection.name,
                "connected_at": connection.connected_at,
            }
            if connection
            else None
        ),
    }


def begin(db: Session, actor: User, session_token: str):
    require_configuration()

    state = secrets.token_urlsafe(48)
    browser = secrets.token_urlsafe(48)
    verifier = secrets.token_urlsafe(48)

    db.execute(
        delete(GmailOAuthState).where(
            GmailOAuthState.expires_at < now(),
        )
    )

    # Keep one pending authorization attempt per application user.
    db.execute(
        delete(GmailOAuthState).where(
            GmailOAuthState.user_id == actor.id,
        )
    )

    db.add(
        GmailOAuthState(
            state_hash=digest(state),
            user_id=actor.id,
            session_hash=digest(session_token),
            browser_hash=digest(browser),
            verifier_encrypted=cipher()
            .encrypt(
                verifier.encode(),
            )
            .decode(),
            expires_at=now() + timedelta(minutes=10),
        )
    )

    db.commit()

    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )

    parameters = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent select_account",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }

    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        parameters
    )

    return authorization_url, browser


def valid_session(db, session_hash, user_id):
    session = db.get(LoginSession, session_hash)
    user = db.get(User, user_id)

    return bool(
        session
        and session.user_id == user_id
        and aware(session.expires_at) > now()
        and user
        and user.active
    )


async def complete(
    db: Session,
    state: str,
    browser: str,
    code: str | None,
    error: str | None,
):
    require_configuration()

    attempt = db.scalar(
        select(GmailOAuthState)
        .where(
            GmailOAuthState.state_hash == digest(state),
        )
        .with_for_update()
    )

    if (
        not attempt
        or not browser
        or not secrets.compare_digest(
            attempt.browser_hash,
            digest(browser),
        )
    ):
        db.rollback()

        raise HTTPException(
            400,
            "Invalid OAuth state.",
        )

    user_id = attempt.user_id
    session_hash = attempt.session_hash
    expired = aware(attempt.expires_at) <= now()

    verifier = (
        cipher()
        .decrypt(
            attempt.verifier_encrypted.encode(),
        )
        .decode()
    )

    # Consume state before the code exchange to prevent replay.
    db.delete(attempt)
    db.commit()

    if expired or not valid_session(db, session_hash, user_id):
        raise HTTPException(
            400,
            "OAuth session expired.",
        )

    if error:
        return "cancelled" if error == "access_denied" else "failed"

    if not code:
        raise HTTPException(
            400,
            "Missing authorization code.",
        )

    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
            },
        )

        if token_response.status_code != 200:
            raise HTTPException(
                502,
                "Google authorization failed.",
            )

        tokens = token_response.json()
        granted = set(tokens.get("scope", "").split())

        email_granted = bool(
            granted
            & {
                "email",
                "https://www.googleapis.com/auth/userinfo.email",
            }
        )

        profile_granted = bool(
            granted
            & {
                "profile",
                "https://www.googleapis.com/auth/userinfo.profile",
            }
        )

        if (
            not {"openid", GMAIL_SCOPE}.issubset(granted)
            or not email_granted
            or not profile_granted
        ):
            return "permissions_missing"

        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")

        if not access_token or not refresh_token:
            return "reconnect_required"

        headers = {
            "Authorization": "Bearer " + access_token,
        }

        profile_response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers=headers,
        )

        if profile_response.status_code != 200:
            raise HTTPException(
                502,
                "Google profile lookup failed.",
            )

        profile = profile_response.json()

        if (
            not profile.get("sub")
            or not profile.get("email")
            or not profile.get("email_verified")
        ):
            raise HTTPException(
                502,
                "Google did not return a verified profile.",
            )

        # Verify Gmail access without downloading any emails.
        mailbox_response = await client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers=headers,
        )

        if mailbox_response.status_code != 200:
            return "mailbox_unavailable"

    # Serialize connection changes for this application user.
    db.scalar(select(User).where(User.id == user_id).with_for_update())

    db.expire_all()

    if not valid_session(db, session_hash, user_id):
        raise HTTPException(
            400,
            "Application session expired.",
        )

    connection = db.get(GmailConnection, user_id)

    if connection is None:
        connection = GmailConnection(user_id=user_id)
        db.add(connection)

    connection.google_sub = profile["sub"]
    connection.email = profile["email"]
    connection.name = profile.get("name", "")[:255]
    connection.scopes = " ".join(sorted(granted))

    connection.access_token_encrypted = (
        cipher()
        .encrypt(
            access_token.encode(),
        )
        .decode()
    )

    connection.refresh_token_encrypted = (
        cipher()
        .encrypt(
            refresh_token.encode(),
        )
        .decode()
    )

    connection.expires_at = now() + timedelta(
        seconds=int(tokens.get("expires_in", 3600)),
    )

    connection.connected_at = now()

    db.commit()

    return "connected"


async def disconnect(db: Session, actor: User):
    require_configuration()

    db.scalar(select(User).where(User.id == actor.id).with_for_update())

    connection = db.get(GmailConnection, actor.id)

    if connection:
        token = (
            cipher()
            .decrypt(
                connection.refresh_token_encrypted.encode(),
            )
            .decode()
        )

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": token},
            )

        already_invalid = False

        if response.status_code == 400:
            try:
                already_invalid = response.json().get("error") == "invalid_token"
            except ValueError:
                pass

        if response.status_code != 200 and not already_invalid:
            raise HTTPException(
                502,
                "Google revocation failed. Retry disconnecting.",
            )

        db.delete(connection)

    db.execute(
        delete(GmailOAuthState).where(
            GmailOAuthState.user_id == actor.id,
        )
    )

    db.commit()

    return status(db, actor)
