# QA Summary — Day Builder v0.4

## Local automated checks
- `python -m pytest -q` in `backend`: **23 passed**.
- `node --check web/app.js`: **passed**.
- `python -m alembic upgrade head` from empty SQLite database: **passed**.
- `curl http://127.0.0.1:8765/api/health`: **200 OK** while local uvicorn was running (nonstandard port used only for test).

## New regression cases
- Preview does not create or replace a stored plan.
- Apply with the preview revision saves the proposed plan.
- A calendar meeting created after preview rejects the old revision with HTTP 409 and leaves the original plan intact.
- Done blocks are carried forward during preview and apply.
- OAuth diagnostics never disclose secret values and reject a foreign `Origin`.
- OAuth start is disabled before setting credentials.

## Known limitations
- Live Google and Microsoft OAuth credentials were not provided: real provider flow not tested.
- Chromium direct HTTP navigation blocked by the container environment policy (`net::ERR_BLOCKED_BY_ADMINISTRATOR`), so full real-server browser E2E **not passed**. However a browser UI smoke test with stubbed API responses confirmed preview, apply and both OAuth setup cards without JavaScript exceptions.
- React dependencies could not be installed from npm in this environment; React build and its E2E are unverified.
- For daily use on Windows prefer FastAPI's bundled no-build UI.
- This is a single-user local app, not secure to expose directly on the public internet.
- Existing legacy API `/api/plans/generate` still writes directly for backward compatibility; built-in UI and updated React use preview/apply.
