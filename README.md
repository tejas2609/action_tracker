# Action Tracker

### AI-powered commitment intelligence for meetings and email

Action Tracker turns meeting discussions and incoming emails into clear, reviewable work. It identifies actions, owners, deadlines, and dependencies, helping teams track progress and preserve the context behind each commitment.

Built with Angular, FastAPI, PostgreSQL, and LangChain, the application combines structured AI extraction, natural-language search, Gmail integration, and human review.

## Features

| Feature | Description |
| --- | --- |
| Meeting analysis | Extract commitments, owners, deadlines, conditions, and supporting statements from transcripts. |
| Commitment tracking | Manage ownership, progress, and active, completed, or cancelled status. |
| Deadline dashboard | View missed deadlines and upcoming tasks in separate paginated cards. |
| Dependencies and blockers | Visualize task relationships and analyze blockers. |
| Natural-language search | Find commitments using questions such as “What do I have to send to Omar?” |
| Gmail integration | Connect Google accounts through OAuth with profile and read-only email permissions. |
| Email review | Review, edit, accept, or reject tasks proposed from incoming emails. |
| Related emails | Attach relevant emails to commitments with explanations and readable source text. |
| Follow-up assistance | Generate contextual follow-up drafts. |
| Profiles and teams | Edit profiles and manage reporting relationships and team membership. |

## Workflow

### Meeting commitments

1. Submit a meeting transcript.
2. AI extracts commitments and supporting context.
3. Review the findings before adding commitments.
4. Track execution through deadlines, progress, and dependencies.

### Incoming emails

1. Connect Gmail through **Integrations**.
2. The worker establishes a baseline and checks new incoming messages.
3. AI compares each email with the application user's commitments.
4. New assignments or requests become proposals under **Commitments → Review**.
5. Clearly related emails become attachments to existing commitments.
6. Unrelated email content is discarded.

For example:

- “Please send Omar the access request tomorrow” can become a review proposal.
- “The access request deadline has been extended by three days” can attach to the existing commitment.

Proposals require acceptance before becoming active. Attaching an email does not automatically change a commitment's deadline or status.

## Technology Stack

- **Frontend:** Angular 19, TypeScript, RxJS, Angular Material icons, SCSS
- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy
- **Database:** PostgreSQL, Alembic
- **AI:** LangChain, Groq
- **Email:** Gmail API, Google OAuth, encrypted credential storage

## Project Structure

```text
backend/
  app/
    ai/             # AI provider integration
    api/            # HTTP endpoints
    core/           # Configuration, authentication, and database
    models/         # Database models
    repositories/   # Shared data access
    schemas/        # Validation contracts
    services/       # Business logic and AI workflows
    email_worker.py # Background Gmail processing
  migrations/
  requirements.txt

frontend/
  src/app/
    core/           # Shared services, guards, and interceptors
    layout/         # Application shell, header, and sidebar
    features/       # Feature components and services
    shared/         # Reusable UI components
```

Angular components use separate TypeScript, HTML, and SCSS files. Gmail fetching, AI classification, and review operations are separated into backend services.

## Prerequisites

- Node.js 22 LTS and npm
- Python 3.11 or later
- PostgreSQL
- A Groq API key
- A Google Cloud project with Gmail API enabled

## Local Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Create the database

Run using a PostgreSQL administrator account:

```sql
CREATE USER tracker WITH PASSWORD 'tracker';
CREATE DATABASE tracker OWNER tracker;
```

These credentials are intended for local development.

### 3. Install backend dependencies

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS or Linux:**

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Ensure `requirements.txt` includes the LangChain integration packages and `cryptography`, alongside the existing backend dependencies.

### 4. Configure environment variables

Create `backend/.env`:

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
```

Generate the encryption key once:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the result into `INTEGRATION_TOKEN_KEY`. Keep this key private and stable. Replacing it without migrating existing credentials prevents their decryption.

The host-only Groq base URL shown above is for the LangChain `ChatGroq` integration.

### 5. Configure Google OAuth

In [Google Cloud Console](https://console.cloud.google.com/):

1. Enable **Gmail API**.
2. Configure Google Auth Platform branding.
3. Select an **External** audience for personal Gmail accounts.
4. Keep the application in **Testing** during development and add your test accounts.
5. Add these scopes:

```text
openid
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
https://www.googleapis.com/auth/gmail.readonly
```

6. Create an OAuth client of type **Web application**.
7. Register this exact redirect URI:

```text
http://localhost:8000/api/integrations/gmail/callback
```

8. Add the client ID and secret to `backend/.env`.

### 6. Apply database migrations

From the backend directory:

```bash
alembic upgrade head
```

### 7. Start the backend

```bash
uvicorn app.main:app --reload --port 8000 --no-access-log
```

API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

The access-log option prevents development request logs from recording OAuth authorization codes in callback URLs.

### 8. Start the frontend

In another terminal:

```bash
cd frontend
npm install
npm start
```

Open [http://localhost:4200](http://localhost:4200).

The Angular development proxy forwards `/api` requests to FastAPI. Use `localhost` consistently for the frontend and Google callback.

### 9. Start the email worker

Activate the backend virtual environment in another terminal:

```bash
cd backend
python -m app.email_worker
```

Connect Gmail through **Integrations**. Allow the worker to establish its baseline before sending a test email.

The worker checks connected accounts on a repeating cycle with a 30-second pause after processing. It runs independently of the browser.

Without the worker, use **Commitments → Review → Check Gmail** to process a batch manually.

## Development Login

Use an existing user's name in lowercase and the shared development password `pass`.

```text
Username: ben
Password: pass
```

The connected Google account belongs to the application profile that authorized it. A different Google profile name can affect AI ownership interpretation unless supplied as an identity alias.

Replace the shared login mechanism before enabling personal Gmail connections for real users.

## Email Data Handling

- Google access and refresh tokens are encrypted in PostgreSQL.
- Google credentials are not returned to the frontend.
- Unrelated email bodies are not retained.
- Message IDs, mailbox identity, and processing outcomes are retained for duplicate prevention.
- Review proposals retain derived task information and source metadata.
- Original proposal emails are fetched from Gmail on demand.
- Attached emails retain bounded plain-text content and an explanation.
- Users can remove email attachments.
- Email content required for classification is transmitted to the configured AI provider.
- Gmail access is read-only. The application does not send, modify, or mark emails as read.

## Current Limitations

- Scanning starts from the first baseline; historical mailbox backfill is disabled.
- Expired Gmail history causes a fresh baseline, skipping the expired gap.
- Email detection uses polling rather than instant push notifications.
- Matching uses thread associations and a bounded text-ranked shortlist, so some semantic relationships may be missed.
- AI classification reads the first 12,000 characters of an email.
- Stored email text is limited to 100,000 characters.
- Binary email attachments are not analyzed.
- AI interpretation requires review and is not guaranteed to be correct.
- Email attachments do not automatically update deadlines or completion status.
- Registration, scheduled reminders, and automatic escalations are not implemented.

## Build and Validation

Build the frontend:

```bash
cd frontend
npm run build
```

Check database migration status:

```bash
cd backend
alembic current
```

Validate these workflows against a development database and Google test account:

- Meeting extraction and review
- Search ownership and organization isolation
- Gmail connection and disconnect
- Email proposal acceptance and rejection
- Related-email attachment and removal
- Duplicate prevention during repeated scans

## Deployment Notes

- Replace development authentication with secure individual credentials.
- Use HTTPS and restrict allowed origins.
- Register production OAuth redirect URLs.
- Set `OAUTH_COOKIE_SECURE=true`.
- Run FastAPI and the email worker as separate managed processes.
- Serve the Angular production build through a web server with `/api` routing.
- Keep secrets out of version control.
- Pin dependencies, back up PostgreSQL, and redact sensitive logs.

The Angular development proxy is not included in production builds.

Gmail read-only is a restricted scope. Public distribution requires Google verification subject to applicable exemptions. Server-side handling of restricted Gmail data can require a security assessment.

External Testing applications requesting Gmail access receive refresh tokens that expire after seven days.

## References

- [Google OAuth web server flow](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Gmail permission scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Gmail history API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
- [Refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)

## Author

**Tejas Murkya**

[GitHub](https://github.com/tejas2609) · [LinkedIn](https://linkedin.com/in/tejas-murkya)
