# Validation — 5 October 2026

- 27 backend tests pass.
- Covered: V1 review and continuity, source-line preservation, user ownership, same-organization visibility, owner/manager editing, cross-organization access rejection, personal counts, attention pagination (10 per page), graph context, chat persistence/cursor/isolation, contextual follow-up delivery and audit events, disabled attachment uploads, session-specific logout, dependency-cycle rollback, cached blocker invalidation, rejection of AI analysis generated against outdated context, and deletion preserving chat messages.
- V1 migration 001 → 002 preserves legacy data and maps owners. Downgrade to 001 → upgrade to 002 also passes. These migration checks use SQLite; foreign keys are enabled for route/deletion tests.
- Angular production build passes strict TypeScript and template compilation.
- Initial raw bundle: 366.60 KB. Estimated transfer: 101.63 KB, excluding remote font requests. Feature routes are lazy-loaded.
- PostgreSQL and Docker execution were not available in this environment, so their runtime behavior remains unverified.
- Browser rendering/interaction checks were attempted, but the browser blocked access to the local development URL with ERR_BLOCKED_BY_CLIENT. No screenshot or visual QA claim is made.
- Live AI calls were not tested because no authorized local API key was supplied. Provider-independent workflows use injected deterministic AI fixtures.

This is a runnable demo V2 with persistent data and demo user sessions. It is not a production-authenticated deployment. See README and UPGRADE for setup and boundaries.
