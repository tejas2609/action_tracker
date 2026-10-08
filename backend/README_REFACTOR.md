# Action Tracker backend refactor

The frontend is unchanged. Existing OpenAPI paths, request schemas and declared responses were compared with the uploaded backend and match. An `X-Request-ID` response header is added.

## Run

1. Keep your existing backend `.env` locally, or copy `.env.example` to `.env` and fill in your settings. Real credentials are deliberately excluded from this archive.
2. Create a virtual environment and run `python -m pip install -r requirements.txt`.
3. Back up your database, then run `python -m alembic upgrade head` from this directory. Revision 006 follows your existing revision 005. Do not use `create_all` to upgrade an existing database.
4. Run `python -m uvicorn app.main:app --reload`.
5. If using automatic Gmail scans, start the existing worker separately: `python -m app.email_worker`.

The existing development login still uses username plus the existing `pass` password. This refactor does not change authentication policy.

## Structure

| Folder | Responsibility |
| --- | --- |
| `app/api` | Request parameters, dependencies, response and cookie handling; delegates work to services |
| `app/schemas` | API input validation; profile, chat and email proposal contracts extracted from routes |
| `app/services` | Feature workflows, permissions, graph/risk calculations, profile and messaging operations |
| `app/repositories` | Organization-scoped commitment access, targeted event retrieval, shared user/session/message queries |
| `app/models` | SQLAlchemy entities, including operational logs |
| `app/core` | Configuration, database sessions, authentication and request logging |
| `app/ai` | Provider protocol, configured implementation and lifecycle |
| `migrations` | Existing migration history plus revision 006 |
| `tests` | New refactor/provider/logging/migration checks |
| `scripts` | Reproducible CPU graph benchmark |

`services/commitment_api.py` contains the commitment read/view and edit orchestration previously embedded in routes. `workflow.py` remains the meeting/commitment workflow. Gmail OAuth and mailbox adapters keep their existing modules to avoid breaking integration imports. Feature services retain some transactional SQL where extracting it would only add forwarding layers; this is not a complete conversion to repository classes for every feature.

## Inspection findings and changes

- Route files mixed validation, business decisions and SQL. Routes now delegate profile, chat, authentication, dashboard, graph and commitment operations; request validation models have their own modules.
- Risk assessment and descendant traversal repeatedly scanned every dependency edge. `DependencyGraph` indexes incoming and outgoing edges once per snapshot. Cycle checks still use visited sets and preserve behavior.
- Commitment listing previously calculated descendant impact for every organization commitment before pagination. It now calculates impact only for returned page items. Risk filtering/order still evaluate the organization snapshot to preserve derived risk semantics and cross-owner dependencies.
- Timeline and follow-up operations loaded all organization events and discarded unrelated ones. `Store.events_for` now performs a scoped, ordered query for one commitment. Follow-up history is kept complete to preserve existing behavior.
- Added event timeline, reverse dependency, owner/status and chat cursor indexes. Verify PostgreSQL query plans against your actual data before claiming database speedups.
- The original provider imported LangChain packages absent from requirements, imported OpenAI without implementing it, and printed extracted meeting content. The replacement uses the existing HTTPX dependency, a reusable connection pool, JSON validation and a total request timeout. Raw meeting extraction and provider error bodies are no longer logged.
- AI meeting matching receives selected commitment fields rather than risk, impact and other unused fields. Existing empty-result recheck behavior and input-grounded review are retained.
- Existing persistent blocker-analysis cache remains: its context hash includes risk/graph state, so changed context invalidates the result. The stale-generation check is retained. No cross-user response cache or new infrastructure was added.
- PostgreSQL connection pool limits and log level are configurable.

## Database logs

Revision 006 adds independent `auth_logs`, `general_logs` and `error_logs` tables. Each stores timestamp (UTC), action, request ID, optional actor/organization IDs, HTTP status and processing duration. Error logs additionally store an error type.

Auth requests and 401 responses go to auth logs. Other non-GET requests go to general logs. HTTP errors (including validation failures) and unhandled request exceptions go to error logs. Application console logging also records route template, status, duration and request ID. Successful login stores the actor ID; failed/unauthenticated requests may have null actor IDs. These tables cover HTTP requests, not every background-worker operation or errors deliberately caught inside a service.

Only route templates and metadata are recorded: no query strings, bodies, passwords, bearer tokens, OAuth codes, email content, or provider response bodies. Logs use their own transaction so request rollback does not discard them. Writes run in a worker thread and are best effort: database logging failure is reported to the console without replacing the API response. Duration measures request processing before the log write, not complete client-observed latency. Set a retention policy suited to your usage; no automatic deletion is enabled.

## Add or customize a feature

1. Add request/response models in `app/schemas/<feature>.py`.
2. Put behavior and authorization decisions in `app/services/<feature>.py`. Pass dependencies explicitly rather than importing another route.
3. Put reusable database lookups/persistence in a focused repository; reuse the request database session and organization checks. Own transaction boundaries in the service.
4. Add a thin router in `app/api/<feature>.py` and register it in `app/main.py`.
5. Add models/migrations only when required. Test tenant isolation, permissions and rollback as well as the normal flow.

For a new integration, expose a small protocol and inject its implementation, following `AIProvider`. Do not share a SQLAlchemy session among concurrent tasks. Graph snapshots are local to one operation and must be rebuilt after dependency mutations.

## Switch AI provider

Groq:

```dotenv
AI_PROVIDER=groq
AI_BASE_URL=https://api.groq.com
AI_MODEL=openai/gpt-oss-20b
AI_API_KEY=your-key
```

OpenAI:

```dotenv
AI_PROVIDER=openai
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=your-chat-completions-model
AI_API_KEY=your-key
```

Compatible endpoint:

```dotenv
AI_PROVIDER=compatible
AI_BASE_URL=https://your-provider.example/v1
AI_MODEL=your-model
AI_API_KEY=your-key
```

Restart after changing configuration. Select a model supporting Chat Completions, JSON-object responses, temperature and `max_tokens`; model-specific request fields belong in a new provider implementation. For a different wire protocol, implement `async json(instruction, payload) -> dict`, optionally `close()`, and return it from `get_provider()`. Services use only the JSON protocol. Live provider/model compatibility was not verified with your credentials.

## Validation and measured performance

Run from this directory:

```bash
python -m pytest tests test_team_deadlines.py test_workflow.py::test_api_validation_and_full_flow -q
python -m compileall -q app migrations
python -m scripts.benchmark_graph
```

20 targeted tests passed. They cover graph traversal and cycles, provider switching through HTTP mocks, invalid AI JSON, database logging/redaction, revision 006 upgrade/downgrade, team deadline behavior and an end-to-end meeting/commitment API flow. Static undefined/unused-name checks passed with Ruff (`--select F`). Existing OpenAPI paths and schema definitions match the baseline.

A 500-node chain benchmark calculates descendants for all 500 nodes, compares identical result sets, and reports median of three runs including construction of the new graph index:

| Implementation | Median CPU time |
| --- | ---: |
| Original repeated edge scans | 1,876.69 ms |
| Indexed graph traversal | 22.90 ms |

This is a synthetic CPU measurement, not production HTTP response latency. Long chains still have quadratic total descendant output when every node needs all descendants.

The full inherited suite was also run: 7 passed, 7 failed and 18 had setup errors, matching the baseline results. Many old fixtures omit the now-required commitment organization, still call `/auth/demo-login`, or expect old migration behavior. The baseline used the replacement provider solely to bypass the original missing LangChain imports. Original legacy tests are retained unchanged; targeted tests above verify the current supported API. Do not interpret the full suite as green.

Not verified: live PostgreSQL migration history/constraints and query plans, real Gmail OAuth/scanning, real Groq/OpenAI calls, load/concurrency behavior, or production response latency. Synchronous SQLAlchemy operations remain inside existing async feature workflows; a full async database conversion needs PostgreSQL integration tests and was not introduced blindly. Gmail scans retain their existing serial processing and locks to avoid sharing a mutable session or duplicating side effects.
