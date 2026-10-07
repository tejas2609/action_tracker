# Action Tracker

Turn meeting discussions into clear commitments, accountable ownership, and measurable progress.

Action Tracker is a meeting-to-action management application built with Angular, FastAPI, and PostgreSQL. It uses AI to extract commitments from meeting transcripts and helps teams track deadlines, dependencies, blockers, and follow-ups.

## Overview

Meeting notes often contain promises that are difficult to track after the discussion ends. Action Tracker connects those promises to responsible users, preserves their original context, and provides a shared view of what needs to happen next.

For example, a statement such as:

> “I’ll send Omar the access request today, before four.”

can become a commitment with an owner, deadline, timing condition, and supporting source statement.

The recorded action is requesting approval. It does not imply that approval has been granted.

## Features

| Feature | Description |
| --- | --- |
| Meeting analysis | Extract commitments, owners, deadlines, and conditions from meeting transcripts. |
| Commitment tracking | Monitor progress and manage active, completed, or cancelled commitments. |
| Deadline dashboard | Review missed deadlines and upcoming tasks in separate paginated cards. |
| Dependency visualization | Explore relationships between commitments and their prerequisites. |
| Blocker analysis | Review recorded blockers and unresolved conditions affecting progress. |
| Natural-language search | Find commitments using questions such as “What does Omar need from me?” |
| Follow-up assistance | Generate contextual follow-up messages for commitments. |
| User profiles | View and edit personal profile information. |
| Team management | Managers can add unassigned users to their team and remove direct reports. |

## Application Workflow

1. Sign in using an existing user account.
2. Submit a meeting transcript for analysis.
3. Review the extracted commitments and their supporting statements.
4. Update commitment details and track progress.
5. Monitor deadlines, dependencies, and blockers.
6. Search for relevant commitments and generate follow-ups.

AI-generated results should be reviewed before being treated as confirmed meeting outcomes.

## Technology Stack

| Layer | Technologies |
| --- | --- |
| Frontend | Angular 19, TypeScript, RxJS, SCSS |
| Backend | Python, FastAPI, Pydantic |
| Persistence | PostgreSQL, SQLAlchemy |
| Database migrations | Alembic |
| AI integration | LangChain, Groq |

The backend keeps AI access behind a provider interface so that application services do not depend directly on a particular model SDK.

## Architecture

The frontend separates application layout, shared infrastructure, reusable UI components, and feature-specific code. Each Angular component keeps its TypeScript, HTML, and SCSS in separate files.

The backend separates HTTP endpoints, validation schemas, business logic, database models, and AI integration.

```text
backend/
├── app/
│   ├── ai/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   └── services/
├── alembic.ini
└── requirements.txt

frontend/
├── src/
│   ├── app/
│   │   ├── core/
│   │   ├── features/
│   │   ├── layout/
│   │   └── shared/
│   └── styles.scss
├── angular.json
├── package.json
└── proxy.conf.json
```

## Prerequisites

- Node.js 22 LTS and npm
- Python 3.11 or later
- PostgreSQL
- A Groq API key
- Git

## Local Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Create the PostgreSQL database

Connect with a PostgreSQL administrator account and run:

```sql
CREATE USER tracker WITH PASSWORD 'tracker';
CREATE DATABASE tracker OWNER tracker;
```

These credentials are for local development. Use separate credentials and appropriate privileges for deployed environments.

### 3. Configure the backend

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
```

For the LangChain `ChatGroq` integration, use the host-only base URL shown above. Adding `/openai/v1` can cause a duplicated request path.

### 4. Install backend dependencies

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

The LangChain integration requires `langchain-core`, `langchain-groq`, and `langchain-openai`. If they have not yet been added to `requirements.txt`, install them:

```bash
python -m pip install langchain-core langchain-groq langchain-openai
```

### 5. Apply database migrations

Run from the `backend` directory:

```bash
alembic upgrade head
```

### 6. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive API documentation is available at:

http://localhost:8000/docs

### 7. Start the frontend

Open a second terminal from the repository root:

```bash
cd frontend
npm install
npm start
```

Open the application at:

http://localhost:4200

The Angular development proxy forwards `/api` requests to the backend on port `8000`.

## Development Authentication

The current login flow uses an existing user's name in lowercase as the username and `pass` as the shared development password.

For example:

```text
Username: ben
Password: pass
```

Registration is not currently part of the application.

This authentication flow is for development and demonstration. Production deployment requires individual password hashing, secure credential management, and an appropriate session lifecycle. Disabling demo login alone does not implement production authentication.

## Configuration Reference

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string. |
| `DEMO_LOGIN_ENABLED` | Enables the development login flow. |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. |
| `AI_PROVIDER` | Selects the implemented AI provider. |
| `AI_BASE_URL` | Provider endpoint configuration. |
| `AI_MODEL` | Model identifier used for AI requests. |
| `AI_API_KEY` | Provider API credential. |
| `AI_TIMEOUT_SECONDS` | AI request timeout. |
| `AI_MAX_OUTPUT_TOKENS` | Maximum generated output tokens per request. |
| `AI_JSON_MODE` | Requests JSON-formatted model responses. |

Backend settings load configuration from environment variables and `backend/.env`. Restart the backend after changing configuration.

## Build and Validation

Build the frontend:

```bash
cd frontend
npm run build
```

Build output is generated under `frontend/dist/`.

Check database migration status:

```bash
cd backend
alembic current
```

Apply outstanding migrations:

```bash
alembic upgrade head
```

Before releasing changes, verify login, meeting analysis, commitment updates, dashboard pagination, search ownership, and team management against a development database.

## Deployment Considerations

The application currently includes development authentication. Complete the authentication work before exposing it publicly.

For deployment:

- Serve the Angular production build through a static web server.
- Route `/api` requests to FastAPI through a reverse proxy.
- Run the backend without `--reload`.
- Use HTTPS and restrict allowed origins.
- Store credentials in environment variables or a secret manager.
- Apply database migrations as a controlled deployment step.
- Configure database backups and application monitoring.
- Keep transcripts, credentials, and sensitive record content out of logs.
- Pin dependencies and maintain reproducible installation files.

The Angular development proxy is not included in the production build. Configure equivalent API routing in the deployed environment.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Database connection fails | Confirm PostgreSQL is running and `DATABASE_URL` is correct. |
| Database tables are missing | Run `alembic upgrade head` from `backend/`. |
| AI authentication fails | Check `AI_API_KEY` and restart the backend. |
| Groq reports an unknown request URL | Use `AI_BASE_URL=https://api.groq.com` with `ChatGroq`. |
| AI output exceeds its token budget | Reduce transcript size or increase the configured output limit. |
| Search returns no commitments | Check generated ownership filters and title/source-statement matching. |
| Frontend API calls fail | Confirm the backend port and development proxy configuration. |

## Current Limitations

- Login uses a shared development password.
- Registration is not implemented.
- AI extraction and search interpretation can require correction.
- Deadline cards display task status; automated reminder delivery and escalation scheduling are not yet implemented.
- Follow-up generation does not imply that a message has been sent.

## Contributing

Keep business logic in backend services and feature behavior in the relevant Angular feature folder. Reuse shared services and UI components where appropriate.

Include database migrations with schema changes, document configuration changes, and describe validation performed in each pull request.