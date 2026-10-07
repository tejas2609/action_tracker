# Action Tracker V2

A commitment control center with organization users, personal dashboards, dependency graphs, a right-side detail drawer and persistent direct chat.

## Existing V1 installation

Read **UPGRADE.md**. Keep your existing database and copy your existing `.env`. Apply migration 002; do not manually create tables or delete your V1 database.

## Quick start with Docker

1. Copy `backend/.env.example` to `backend/.env` and set `AI_API_KEY`.
2. From this directory run `docker compose up --build`.
3. Open http://localhost:8080 and choose a demo user.

Compose runs PostgreSQL, migrations, FastAPI and nginx. Compose overrides DATABASE_URL to its database service. If your current V1 database runs outside Docker, follow the local upgrade instructions instead to keep using that database.

## Local setup (no virtual environment required)

Python 3.12 and Node.js 22 are recommended. PostgreSQL must be running.

```powershell
cd backend
python -m pip install -r requirements.txt
# Copy .env.example to .env if starting fresh. Set DATABASE_URL and AI_API_KEY.
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm ci
npm start
```

Application: http://localhost:4200. API documentation: http://localhost:8000/docs.

## What's included

- Demo organization login, random bearer sessions stored hashed on the server, eight-hour expiry and session-specific sign-out.
- Ten dummy organization members, plus imported V1 owner names. Organization directory with search, team and role filters.
- Personal dashboard: total promises, active, on-track, at-risk, blocked, deadline-passed and completed counts. Attention results use page size 10.
- Dashboard graph contains your commitments and their connected dependency chains.
- My Commitments defaults to your own records only. List filtering/pagination, inline status updates, list/graph toggle.
- Graph defaults to your commitments plus their immediate prerequisites and immediate dependents. Entire-chain mode is available. Scroll and zoom controls render every returned node, including disconnected personal commitments.
- Right-side drawer: details/owner/status/progress, contextual follow-up, live blockers, graph/dependency edits, source quotation and audit timeline. Escape and close button dismiss it; keyboard focus stays in the drawer.
- Follow-up recipient defaults to the owner when it is another user, or a prerequisite owner for your own promise. You can choose another colleague. Generate, review/edit, and explicitly Send to chat. The message includes a commitment link; sending creates a timeline event.
- Direct chat is stored in PostgreSQL, refreshes every three seconds, and supports loading older messages. Open two different browsers/profiles or a normal and private window to test conversations as different users.
- Attachment button is disabled. Attachment table, metadata schema and capability endpoint exist; upload endpoint returns 501 and attachment IDs in messages are rejected.
- Blocker signals refresh every five seconds while the drawer is open. AI explanations are cached against commitment, dependency, progress, deadline and downstream context; changed context triggers regeneration. AI failures leave deterministic blocker signals visible and provide a manual retry.
- AI transcript extraction uses numbered source lines; the backend copies source text. JSON-generation errors have one text-mode retry followed by JSON/Pydantic validation.
- Meeting deletion retains its impact preview and recursively deletes related dependency components. Existing chat messages are preserved; links to deleted commitments become null.

## User ownership and permissions

A commitment has both display name `owner` and foreign key `owner_id`. V1 records are matched by owner name during migration; previously unseen owners become imported directory users. Review requires selecting an active organization user, preventing new orphan ownership.

A signed-in user sees only their own commitments in the main list and dashboard. Other organization promises appear as graph/blocker context and can be inspected in the drawer. Meeting review and directory/chat are shared within the organization. Only the owner or the seeded Product Manager role can edit a commitment or its dependencies. Changing ownership removes it from the previous owner's personal view.

The API enforces organization boundaries for records and conversations. **Demo sign-in deliberately lets anyone select a seeded user without a password.** It is a testing feature, not production identity verification. Do not expose this version publicly. `DEMO_LOGIN_ENABLED=false` disables demo login; it does not install a production identity provider. Integrate real authentication before deployment.

## Database

V1: meetings, commitments, dependencies, events, alembic_version.

V2 adds organizations, users, login_sessions, conversations, messages and attachments, plus ownership and cached analysis columns. Migration `002` upgrades `001` and preserves existing records. Schema downgrade removes V2 users/chat/session data; use upgrades for normal operation.

## Architecture

Backend: `app/api` REST boundaries, `app/services` workflow/intelligence/messaging/deletion, `app/repositories` scoped persistence, `app/models` SQLAlchemy entities, `app/schemas` validation, `app/ai` provider contract and compatible adapter, `app/core` settings/database/auth, versioned Alembic migrations.

Frontend: lazy-loaded features in `src/app/features`, typed API/session/panel services in `core`, reusable table/pagination/graph/drawer/chat components in `shared`. Signals and OnPush change detection are used. No frontend API key.

## Limits

Risk remains an explainable heuristic, not a trained predictive model. Actual work completion, approvals and progress are user-managed. Dates are date-only; the team's backend calendar date is used. Chat uses polling rather than WebSockets. Attachment upload/download, notifications/unread badges, production authentication, organization administration and external integrations are not included. Very large workspaces need optimized server graph queries and canvas virtualization; V2 renders the complete graph in scrollable SVG without pagination or hidden nodes. Concurrent graph writes/deletion lack full locking; use one trusted demo organization for evaluation. AI availability/model quotas depend on your provider account.

## Validation

```powershell
cd backend
python -m pytest -q
cd ../frontend
npm run build -- --configuration production
```

See VALIDATION.md for results and unverified runtime checks.
