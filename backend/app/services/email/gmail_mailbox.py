import base64
from datetime import datetime, timedelta, timezone
from email.message import Message
from html.parser import HTMLParser

import httpx

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.integrations import GmailConnection
from app.services.email.gmail_integration import aware, cipher, now

MAX_BODY_CHARS = 100_000


class PlainTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag in ("br", "p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def html_to_text(value):
    parser = PlainTextParser()
    parser.feed(value)

    return "".join(parser.parts)


class GmailMailbox:
    BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id

        connection = db.get(GmailConnection, user_id)

        if not connection:
            raise HTTPException(409, "Connect Gmail first.")

        self.google_sub = connection.google_sub
        self.email = connection.email
        self.http = None

    async def __aenter__(self):
        self.http = httpx.AsyncClient(timeout=30)
        return self

    async def __aexit__(self, *args):
        await self.http.aclose()

    async def access_token(self, force=False):
        connection = self.db.scalar(
            select(GmailConnection)
            .where(GmailConnection.user_id == self.user_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if not connection or connection.google_sub != self.google_sub:
            self.db.rollback()

            raise HTTPException(
                409,
                "Gmail connection changed. Retry.",
            )

        if force or aware(connection.expires_at) <= now() + timedelta(seconds=60):
            refresh_token = (
                cipher()
                .decrypt(
                    connection.refresh_token_encrypted.encode(),
                )
                .decode()
            )

            response = await self.http.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code != 200:
                self.db.rollback()

                raise HTTPException(
                    409,
                    "Gmail authorization expired. Disconnect and reconnect Gmail.",
                )

            tokens = response.json()

            connection.access_token_encrypted = (
                cipher()
                .encrypt(
                    tokens["access_token"].encode(),
                )
                .decode()
            )

            if tokens.get("refresh_token"):
                connection.refresh_token_encrypted = (
                    cipher()
                    .encrypt(
                        tokens["refresh_token"].encode(),
                    )
                    .decode()
                )

            connection.expires_at = now() + timedelta(
                seconds=int(tokens.get("expires_in", 3600)),
            )

        access_token = (
            cipher()
            .decrypt(
                connection.access_token_encrypted.encode(),
            )
            .decode()
        )

        self.db.commit()

        return access_token

    async def get(self, path, params=None):
        for attempt in range(2):
            token = await self.access_token(force=attempt == 1)

            response = await self.http.get(
                self.BASE_URL + path,
                params=params,
                headers={"Authorization": "Bearer " + token},
            )

            if response.status_code == 401 and attempt == 0:
                continue

            if response.status_code == 404:
                raise HTTPException(404, "Gmail resource is unavailable.")

            if response.status_code != 200:
                raise HTTPException(
                    502,
                    "Gmail request failed. Retry later.",
                )

            return response.json()

        raise HTTPException(409, "Reconnect Gmail.")

    async def profile(self):
        return await self.get("/profile")

    async def messages(self, query, page_token=None):
        params = {
            "q": query,
            "maxResults": 100,
        }

        if page_token:
            params["pageToken"] = page_token

        return await self.get("/messages", params)

    async def history(self, history_id, page_token=None):
        params = {
            "startHistoryId": history_id,
            "historyTypes": "messageAdded",
            "maxResults": 100,
        }

        if page_token:
            params["pageToken"] = page_token

        return await self.get("/history", params)

    async def message(self, message_id):
        raw = await self.get(
            "/messages/" + message_id,
            {"format": "full"},
        )

        payload = raw.get("payload", {})

        headers = {
            item["name"].lower(): item["value"] for item in payload.get("headers", [])
        }

        async def extract(part):
            if part.get("filename"):
                return ""

            children = part.get("parts", [])

            if children:
                # Prefer plain text in multipart/alternative.
                if part.get("mimeType") == "multipart/alternative":
                    plain = next(
                        (
                            child
                            for child in children
                            if child.get("mimeType") == "text/plain"
                        ),
                        None,
                    )

                    if plain:
                        return await extract(plain)

                texts = []

                for child in children:
                    texts.append(await extract(child))

                return "\n".join(texts)

            mime_type = part.get("mimeType", "")

            if mime_type not in ("text/plain", "text/html"):
                return ""

            body = part.get("body", {})
            data = body.get("data")

            if not data and body.get("attachmentId"):
                attachment = await self.get(
                    "/messages/" + message_id + "/attachments/" + body["attachmentId"],
                )

                data = attachment.get("data")

            if not data:
                return ""

            decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

            part_headers = {
                item["name"].lower(): item["value"] for item in part.get("headers", [])
            }

            content_type = Message()
            content_type["content-type"] = part_headers.get(
                "content-type",
                mime_type,
            )

            charset = content_type.get_content_charset() or "utf-8"

            try:
                text = decoded.decode(charset, errors="replace")
            except LookupError:
                text = decoded.decode("utf-8", errors="replace")

            return html_to_text(text) if mime_type == "text/html" else text

        text = (await extract(payload)).strip()

        return {
            "id": raw["id"],
            "thread_id": raw.get("threadId", ""),
            "subject": headers.get("subject", "")[:1000],
            "sender": headers.get("from", "")[:1000],
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "received_at": datetime.fromtimestamp(
                int(raw["internalDate"]) / 1000,
                timezone.utc,
            ),
            "labels": raw.get("labelIds", []),
            "body_text": text[:MAX_BODY_CHARS],
            "truncated": len(text) > MAX_BODY_CHARS,
        }
