# Upgrade your current project to V2

Keep the current V1 folder as a backup. Extract this archive as a separate `action-tracker-v2` folder next to it. Stop both running terminals with Ctrl+C.

## 1. Copy your existing environment file

Using your current directory layout:

```powershell
Copy-Item "E:\50days\1\action-tracker-v1\backend\.env" "E:\50days\1\action-tracker-v2\backend\.env"
```

Keep DATABASE_URL pointing to the SAME working V1 database. Keep your private Groq API key locally; do not paste it into chats. No secrets are included in this archive. The source package already includes the JSON retry and source-line quotation fixes.

## 2. Install and migrate (no venv required)

```powershell
cd "E:\50days\1\action-tracker-v2\backend"
python -m pip install -r requirements.txt
python -m alembic current
python -m alembic upgrade head
python -m alembic current
python -m uvicorn app.main:app --reload
```

Your previous migration should be `001`. After upgrade it should be `002 (head)`. The migration creates demo users and chat tables and maps existing promises to users by owner name. It keeps your meetings, promises, dependencies and history.

If the database already contains incompatible tables from another implementation, do not use `alembic stamp` to pretend it was migrated; resolve that schema separately. This upgrade targets the V1 package delivered in this conversation.

## 3. Start Angular in another terminal

```powershell
cd "E:\50days\1\action-tracker-v2\frontend"
npm ci
npm start
```

Open http://localhost:4200. Choose a demo user whose name matches the owner of your existing commitments. Selecting Tejas will not show promises owned by Sarah; this is intentional personal scoping.

## 4. Try the new workflow

1. Choose Sarah or another member with existing promises.
2. Dashboard shows their metrics and attention page (10 per page).
3. Commitments → change a status directly in the list, then switch to Graph.
4. Open a row/node: the detail drawer opens from the right. Close with × or Escape.
5. Edit dependencies and watch blocker signals and AI context update.
6. Select a follow-up recipient, generate/edit the draft, and Send to chat.
7. Users → filter by team/role → Message a colleague.
8. Open a private window, choose that colleague, then open your conversation to see messages from the first user. Text messaging works without an AI key. Attachments remain disabled.

No external email/Slack messages are sent; messages remain inside Action Tracker's own database.

## Docker upgrades

If V1 was run entirely with Compose, retain the same Compose project/volume when rebuilding V2 so you retain the database. A new folder may produce a new project name and empty volume. Set `COMPOSE_PROJECT_NAME` to your existing project name or explicitly configure the existing volume before starting. Local PostgreSQL users should use the local commands above rather than accidentally switching to Docker's separate database.
