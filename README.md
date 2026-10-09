# Action Tracker

### AI-powered commitment intelligence for meetings and email

Action Tracker turns meeting discussions and incoming emails into reviewable commitments with owners, deadlines, conditions, and dependencies. Teams can track individual commitments and treat each meeting agenda as a shared task, with progress, next actions, and dependency analysis.

Built with Angular, FastAPI, PostgreSQL, and a replaceable AI provider integration.

## Features

| Feature | Description |
| --- | --- |
| Meeting capture | Add a title, date, transcript, participants, and public/private visibility in a right-side drawer. |
| Meeting analysis | Extract commitments, owners, deadlines, conditions, and supporting statements from transcripts. |
| Review drawer | After saving, the creation drawer closes and resets; analysis and extracted findings appear in a separate drawer that can be reopened from meeting history. |
| Manual commitments | Create commitments without a transcript, with optional meeting association, prerequisites, deadline, progress, condition, and blocker. |
| Commitment tracking | Manage ownership, progress, and active, completed, or cancelled status. |
| Meeting agenda tracker | Track meeting-level progress, completed agendas, descriptive next steps, and the next three outstanding team commitments. |
| Dependency analysis | View dependencies within a meeting and upstream dependencies across meetings, including full/partial coverage. |
| Meeting access | Restrict meeting history and agenda access to participants, their responsible managers, and approved public-meeting requesters. |
| Organization directory | Search public meeting titles and dates and request access without exposing transcripts. |
| Manager request inbox | Responsible managers approve or decline meeting access requests; declined requests can be submitted again with the retry change applied. |
| Deadline dashboard | View missed deadlines and upcoming tasks in paginated cards. |
| Natural-language search | Find commitments using questions such as “What do I have to send to Omar?” |
| Gmail integration | Connect Google accounts through OAuth with profile and read-only email permissions. |
| Email review | Review, edit, accept, or reject tasks proposed from incoming emails. |
| Related emails | Attach relevant emails to commitments with explanations and readable source text. |
| Chat review | Review, edit, accept, or reject tasks proposed from chats shared. |
| Related chats | Attach relevant chats to commitments with explanations and readable source text. |
| Follow-up assistance | Generate contextual follow-up drafts. |
| Profiles and teams | Manage profiles, team membership, and reporting relationships. |
| Operational logging | Separate authentication, general activity, and error log tables with timestamps and request metadata. |

## Workflows

### Meetings

1. Open **Meetings → Add meeting**.
2. Enter the title, date, actual participants, visibility, and transcript. The creator is included as a participant automatically.
3. Click **Save & analyze transcript**.
4. After a successful save, the creation drawer closes and resets. The review drawer opens while analysis runs.
5. Review extracted findings, assign owners, adjust deadlines, and confirm prerequisites or links to existing commitments.
6. Confirm the review to create or link commitments.
7. Close and reopen the review drawer through meeting history.
8. Select the agenda in **Action tracker** to inspect progress, next actions, and dependencies.

If analysis fails after saving, the meeting remains saved and can be analyzed again. Closing the review drawer preserves edits while staying on the Meetings tab; unsaved edits are not guaranteed to survive navigation or a reload.

### Manual commitments

Open **Commitments → Add commitment**. Use the right-side drawer to enter a title, description, deadline, progress, prerequisites, condition, blocker, and optional meeting association. The signed-in user owns the new commitment initially.

### Agenda completion and next actions

- Agenda membership includes distinct commitments created for the meeting and existing commitments linked during review. Repeated mentions do not increase the count.
- Progress is the equally weighted average of linked commitment progress. Completed commitments contribute 100%.
- An agenda is completed only after meeting review, with at least one linked commitment, and every linked commitment having status `completed`.
- Progress is capped at 99% until those completion requirements are met.
- Example: five commitments with progress `100, 0, 0, 0, 0` produce 20% agenda progress.
- Cancelled commitments keep the agenda open. Meetings with no commitments are not automatically completed.
- Completed agendas appear in the **Completed agendas** tab. Reopening or adding a commitment can return an agenda to Active on the next refresh.
- Next steps are generated from stored commitment facts without an additional AI call.
- The timeline shows up to three outstanding team commitments, prioritizing ready work and then deadlines. It is a priority sequence, not a predicted schedule.
- A commitment is ready when active, its immediate prerequisites are completed, it has no blocker, and its condition is absent or met.

Meeting review state (`draft`, `analyzed`, `reviewed`) remains separate from calculated agenda completion state.

### Dependency views

**Within this meeting:** commitments belonging to the selected agenda and their internal dependency edges.

**Across meetings:** the agenda's commitments and their upstream prerequisite closure, including indirect dependencies and prerequisites without an associated meeting.

Arrows point from prerequisite to dependent commitment. Full dependency means every agenda commitment has an upstream path from the external meeting; partial dependency means only some do. Coverage describes structural dependency, while unfinished prerequisite counts indicate remaining work.

The supplied UI labels are **Within this meeting (Inter)** and **Across meetings (Intra)**. Conventionally, intra means within and inter means between; internal API fields use `within` and `across` to avoid ambiguity.

### Meeting visibility and access requests

| Meeting visibility | Discovery | Meeting access | Access requests |
| --- | --- | --- | --- |
| Public | Title and date are discoverable within the organization. | Participants, responsible managers, and approved requesters. | Allowed when active participant managers are configured. |
| Private | Hidden from the organization directory. | Participants and their responsible managers. | Not allowed. |

Public means discoverable and requestable, not unrestricted transcript access.

Managers gain access through participants whose `manager_id` points to them. Matching team names alone does not grant access. Managers otherwise use the same meeting workflow as participants.

1. Search **Organization meetings** below the agenda tracker.
2. Request access to a public meeting, optionally explaining why.
3. The request appears in the in-app inbox of managers responsible for that meeting's participants.
4. Any currently responsible manager can approve or decline it.
5. Approved requesters receive read access, not participant status or analysis/review permission.
6. A declined request can be submitted again when the retry change is applied. This reuses the request record and replaces its decision fields; it is not a complete decision-history audit.

Requests do not send email or external notifications. Changes from another user's browser require a refresh; there are no WebSocket updates.

### Incoming emails

1. Connect Gmail through **Integrations**.
2. The worker establishes a baseline and checks new incoming messages.
3. AI compares each email with the application user's commitments.
4. New assignments or requests become proposals under **Commitments → Review**.
5. Clearly related emails attach to existing commitments.
6. Unrelated email content is discarded.

Proposals require acceptance before becoming active. Attaching an email does not automatically change a commitment's deadline or status.

## Technology Stack

- **Frontend:** Angular 19, TypeScript, RxJS, Angular CDK, SCSS
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, HTTPX
- **Database:** PostgreSQL, Alembic
- **AI:** replaceable Groq, OpenAI, or compatible JSON provider
- **Email:** Gmail API, Google OAuth, encrypted credential storage

The refactored provider uses HTTPX connection reuse and configurable timeouts. LangChain is not required by that provider implementation; retain LangChain dependencies only if other project modules use them.

## Project Structure

```text
backend/
  app/
    ai/                         # Replaceable AI provider
    api/                        # Routes, integrations, access requests
    core/                       # Configuration, auth, database, logging
    features/
      meeting_agendas/          # Domain rules, repository, service, routes
    models/                     # Database models
    repositories/               # Shared data access
    schemas/                    # Validation contracts
    services/                   # Workflows and meeting access policy
    email_worker.py             # Background Gmail processing
  migrations/
  requirements.txt

frontend/
  src/app/
    core/                       # Services, guards, interceptors
    layout/                     # Application shell
    features/
      meetings/
        action-tracker/         # Agenda list, timeline, dependency graph
        meeting-access/         # Public directory and manager inbox
      commitments/              # Commitment list and manual creation
    shared/                     # Reusable components and drawers
```

Agenda calculations are separated from database access and HTTP routing. Frontend API adapters, tracker presentation, and graph rendering are separate so they can be replaced independently.

## Local Setup

### Prerequisites

- Node.js 22 LTS and npm
- Python 3.11 or later
- PostgreSQL
- API credentials for the configured AI provider
- A Google Cloud project with Gmail API enabled if using Gmail

### 1. Clone

```bash
git clone https://github.com/tejas2609/action_tracker.git
cd action_tracker
```

### 2. Create a development database

Run with a PostgreSQL administrator account:

```sql
CREATE USER tracker WITH PASSWORD 'tracker';
CREATE DATABASE tracker OWNER tracker;
```

These credentials are for local development. Use your actual database credentials in `.env`.

### 3. Install backend dependencies

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
```

### 4. Configure `backend/.env`

```dotenv
DATABASE_URL=postgresql+psycopg://tracker:tracker@localhost:5432/tracker
DEMO_LOGIN_ENABLED=true
CORS_ORIGINS=http://localhost:4200

AI_PROVIDER=groq
AI_BASE_URL=https://api.groq.com
AI_MODEL=openai/gpt-oss-20b
AI_API_KEY=your-groq-api-key
AI_TIMEOUT_SECONDS=120
AI_MAX_OUTPUT_TOKENS=8192
AI_JSON_MODE=true

GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/gmail/callback
FRONTEND_URL=http://localhost:4200
INTEGRATION_TOKEN_KEY=your-fernet-key
OAUTH_COOKIE_SECURE=false

LOG_LEVEL=INFO
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
```

Use a model available to your provider account. Gmail variables are needed only for Gmail integration.

Generate the encryption key once:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep `INTEGRATION_TOKEN_KEY` private and stable. Replacing it without migrating stored credentials prevents their decryption. Never commit `.env` or credentials.

### 5. Configure Google OAuth

In [Google Cloud Console](https://console.cloud.google.com/):

1. Enable Gmail API.
2. Configure Google Auth Platform branding and audience.
3. For development with personal Gmail accounts, use External/Testing and add test accounts.
4. Configure these scopes:

```text
openid
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
https://www.googleapis.com/auth/gmail.readonly
```

5. Create a Web application OAuth client.
6. Register `http://localhost:8000/api/integrations/gmail/callback` exactly.
7. Add the client credentials to `.env`.

Consult the Google references below for current verification and token-lifetime requirements before public distribution.

### 6. Apply migrations

From `backend`:

```bash
python -m alembic upgrade head
```

The participant/access migration adds `meetings.visibility`, `meeting_participants`, and `meeting_access_requests`.

Alembic dependencies reference revision IDs, not filenames. In the supplied refactored backend, `006_logs_indexes.py` declares `revision = "006"`; the next migration must therefore use `down_revision = "006"`, not `"006_logs_indexes"`.

Existing meetings default to private in the supplied access migration. Record their actual participants before expecting them to appear in participant/manager history. In pgAdmin Query Tool, inspect:

```sql
SELECT id, title, visibility, organization_id FROM public.meetings;
SELECT id, name, organization_id, manager_id FROM public.users;
```

Then insert one participant row per actual attendee using real IDs from the same organization:

```sql
INSERT INTO public.meeting_participants (meeting_id, user_id)
VALUES ('replace-with-real-meeting-id', 'replace-with-real-user-id')
ON CONFLICT DO NOTHING;
```

Do not execute placeholder strings literally. New meetings save participants through the form; manual backfill is only for existing records. Managers need participant rows only if they attended, not merely to view their direct reports' meetings.

### 7. Start the backend

```bash
python -m uvicorn app.main:app --reload --port 8000 --no-access-log
```

API documentation: [http://localhost:8000/docs](http://localhost:8000/docs).

Disabling Uvicorn access logs avoids recording OAuth codes from callback URLs in those logs. Application logging uses request metadata; ensure other logging layers also redact sensitive URLs.

### 8. Start the frontend

In another terminal:

```bash
cd frontend
npm install
npm start
```

Open [http://localhost:4200](http://localhost:4200). The development proxy forwards `/api` requests to FastAPI. Use `localhost` consistently for the frontend and OAuth callback.

### 9. Start the email worker

In a terminal with the backend virtual environment activated:

```bash
cd backend
python -m app.email_worker
```

Connect Gmail through Integrations and allow baseline initialization before sending a test message. The worker runs independently of the browser, with a 30-second pause after processing. Without the worker, use **Commitments → Review → Check Gmail** to process a batch manually.

### 10. Start the source worker

In a terminal with the backend virtual environment activated:

```bash
cd backend
python -m app.source_worker
```

Start the source worker to enable the engine to process chats, gather context, and relate or form commitments. The worker runs independently of the browser, with a 1-second pause after processing.


## Development Login

For the supplied development login, use an existing user's name in lowercase and password `pass`:

```text
Username: ben
Password: pass
```

This application password is separate from the PostgreSQL password. Replace development authentication before allowing real-user access or personal Gmail connections.

## Adding Features or Replacing Providers

Keep routes focused on validation and responses, business rules in services/domain modules, and database operations in repositories. Reuse the meeting access policy whenever adding an endpoint that returns meeting content.

To switch the supplied compatible provider to OpenAI, set `AI_PROVIDER=openai`, `AI_BASE_URL=https://api.openai.com`, and your account's model and key. Provider-specific behavior belongs in `app/ai/provider.py`. The supplied HTTPX adapter adds the appropriate API path for Groq or OpenAI; its host-only Groq URL is not specific to LangChain.

To replace the database adapter, preserve the agenda repository's `summaries()` and `snapshot()` contracts. To replace graph rendering, preserve the frontend `AgendaGraph` contract and replace `agenda-graph.component.ts`.

## Email Data Handling

- Google access/refresh tokens are encrypted in PostgreSQL and not returned to the frontend.
- Unrelated email bodies are not retained; message identity and processing outcomes support duplicate prevention.
- Review proposals retain derived task data and source metadata. Original proposal emails are fetched from Gmail on demand.
- Related-email attachments retain bounded plain text and an explanation; users can remove them.
- Content required for classification is transmitted to the configured AI provider.
- Gmail access is read-only; the application does not send, modify, or mark emails as read.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| PostgreSQL password authentication fails | Restore the correct `DATABASE_URL`; check whether a terminal environment variable overrides `.env`. |
| Participant insert fails with a foreign-key error | Use existing meeting/user IDs, not placeholder strings, and confirm the database is correct. |
| Meeting history is empty | Check participant rows, manager relationships, organization, and approved access. |
| Organization directory is empty | Only public meetings in the signed-in user's organization are listed; clear search and inspect the API response. |
| Directory returns 500 with auto-correlation | Apply `.correlate(meeting)` inside the participant, manager, and approved-request policy subqueries. |
| Access requests cannot be submitted | Check public visibility and active managers for participants; pending/approved requests cannot be duplicated. |
| Declined request has no retry button | Apply both the backend rejected-request reset and frontend Request again changes. |
| Gmail is not processing messages | Check the worker, OAuth connection, baseline state, provider credentials, and backend logs. |

## Validation and Current Limitations

```bash
# Frontend
cd frontend
npm run build
```

```bash
# Backend
cd backend
python -m alembic current
python -m pytest
```

Run the targeted agenda tests when included:

```bash
python -m pytest -q tests/test_meeting_agendas.py
```

The delivered agenda feature passed eight focused SQLite tests. That does not validate the later participant/access-request changes, live PostgreSQL, Gmail, or Angular browser behavior. The inherited backend suite has known pre-existing failures.

Before using meeting visibility as a production confidentiality boundary, apply and test the same policy on meeting-linked commitment/search/export surfaces. The supplied meeting access changes alone do not change all existing commitment-sharing rules. The current deletion workflow can span linked meetings and needs authorization checks for every affected meeting.

Other limitations:

- Cross-user changes require refresh; no real-time push updates.
- Request retries reuse one record rather than preserving full decision history.
- Large dependency closures and SVG graphs need profiling and may require collapse/virtualization.
- Email scanning begins at a baseline; historical backfill is disabled, and expired history triggers a fresh baseline.
- Email matching uses thread associations and a bounded shortlist, so relationships can be missed.
- Classification reads the first 12,000 email characters; stored attachment text is bounded to 100,000 characters.
- Binary email attachments are not analyzed. AI interpretation requires human review.
- Registration, scheduled reminders, and automatic escalations are not implemented.

Validate participant/manager visibility, private-directory exclusion, cross-organization denial, request approval/rejection/retry, agenda completion/reopening, linked membership, dependency coverage, and Gmail duplicate prevention against a development database.

## Deployment Notes

- Replace development authentication and verify backend authorization on every relevant endpoint.
- Use HTTPS, restricted origins, production OAuth redirects, and `OAUTH_COOKIE_SECURE=true`.
- Run FastAPI and the email worker as separate managed processes.
- Serve the Angular production build with `/api` routing; the development proxy is not included in production builds.
- Keep secrets out of Git, pin dependencies, back up PostgreSQL, and redact sensitive logs.
- Review Google's current Gmail scope, verification, and security requirements before public distribution.

## References

- [Google OAuth web server flow](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Gmail permission scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Gmail history API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
- [Refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)

## Author

**Tejas Murkya**

[GitHub](https://github.com/tejas2609) · [LinkedIn](https://linkedin.com/in/tejas-murkya)
