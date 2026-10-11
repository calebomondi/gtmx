# GTMX

Go-to-market research for a product or service: a user describes an offer,
answers a short interview, and gets offer, market, competition and ICP
analysis. They can then track competitors, find target accounts and draft
outreach.

| App | Where | Port |
|---|---|---|
| Backend API (FastAPI) + agents (LangGraph) | this repo, `backend/`, `agents/` | 8000 |
| Customer app (React + Vite) | this repo, `frontend/` | 5173 |
| Admin console (React + Vite, Turborepo) | separate repo `gtmx-admin`, checked out at `admin_dashboard/` | 5174 |
| Postgres 16 | `docker-compose.yml` | 5432 |

Rules for working on the code (structure, migrations, git flow) are in
[CLAUDE.md](CLAUDE.md). The launch plan and the post-launch TODOs are in
[docs/launch-plan.md](docs/launch-plan.md).

## Setup

Needs: [uv](https://docs.astral.sh/uv/), [Bun](https://bun.sh), Docker.

```bash
cp .env.example .env                 # then fill in the keys (below)
uv sync
docker compose up -d --wait          # Postgres on :5432 (gtmx/gtmx)
uv run alembic upgrade head          # the API refuses to start on an old schema

cd frontend && cp .env.example .env && bun install
cd ../admin_dashboard && cp apps/web/.env.example apps/web/.env && bun install
```

## Configuration

Every backend setting is a field on `config.Settings` (`config.py`); `.env.example`
lists them with comments. The ones you must set:

| Variable | What |
|---|---|
| `DATABASE_URL` | Postgres URI. Local default works with docker compose. |
| `SUPABASE_BASE_URL`, `SUPABASE_SECRET_KEY` | Auth. The secret key never goes to a browser. |
| `DASHSCOPE_API_KEY` | Qwen, the primary LLM. |
| `OPENAI_API_KEY` | OpenRouter key, the LLM fallback when Qwen is down or out of quota. |
| `EXA_API_KEY` | Web search and scraping. |
| `BRIGHTDATA_API_KEY` | LinkedIn / X / Instagram / TikTok profiles. |
| `COMPOSIO_API_KEY` | Users' connected Gmail / LinkedIn / Instagram for outreach. |
| `ADMIN_BOOTSTRAP_EMAILS` | Granted admin at startup (see below). |

Both web apps need `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (the public
anon key) in their own `.env`.

Useful knobs: `LLM_MAX_CONCURRENCY` (LLM calls in flight per provider, default
8), the per-user daily caps (`MAX_*_PER_DAY`), `MONITOR_ENABLED`
(daily competitor re-checks; set `false` on a dev machine to avoid paid runs),
`LLM_PRICES` / `API_CALL_PRICES` (cost estimates shown in the admin console).

Observability is opt-in: `SENTRY_DSN` (backend) and `VITE_SENTRY_DSN` (web apps)
for error reporting, `LANGSMITH_API_KEY` for agent traces (these contain
prompts and scraped pages), `GTMX_LOG_FORMAT=json` for one JSON object per
log line. Every log line is tagged with `run_id` and `user_id`.

## Running

```bash
scripts/dev.sh                                    # API on :8000 with reload
cd frontend && bun run dev                        # customer app on :5173
cd admin_dashboard && bun run dev                 # admin console on :5174
```

Both web apps proxy `/api` to `:8000` in development. `GET /health` reports
the database and the agent runtime.

## Checks (CI runs the same)

```bash
uv run ruff check .
uv run pytest                                      # uses the gtmx_test database
uv run alembic upgrade head && uv run alembic check
cd frontend && bun run build && bun run lint
cd admin_dashboard && bun run build && bun run typecheck && bun run lint
```

`uv run python -m scripts.load_test --runs 10 --cleanup` runs real concurrent
discovery runs (spends LLM and search credit) and reports timings, event-loop
lag, DB pool use and LLM failures.

## Admins

The admin console only lets in accounts whose Supabase `app_metadata.role`
is `admin`; the API checks it on every admin request.

- **First admin:** put their email in `ADMIN_BOOTSTRAP_EMAILS` and restart the
  API after they have signed up once. It is idempotent.
- **More admins:** an admin opens Users → the person → *Make admin*.
- An admin cannot revoke themself, and the last admin cannot be removed. Every
  grant, revoke, suspension, cancel and quota change is in the Audit log.

## Incident runbook

**A user's run is stuck.** Admin console → Runs → open it. The timeline shows
the last step it reached and the cost so far. *Cancel run* stops it and tells
the user an administrator cancelled it. Every run also has a hard timeout.

**The API restarted mid-run.** On startup, runs that were working are marked
failed with "The server restarted…", and the user can start them again. Runs
waiting for the user's answer are unaffected and resume on answer.

**LLM errors (429 / quota / outage).** Logs show `rate_limit` or
`billing` per call. Calls retry with backoff, then fall back to OpenRouter.
Sustained 429s under load: lower `LLM_MAX_CONCURRENCY`. Quota exhausted: top
up DashScope; the fallback keeps runs going meanwhile. The admin Overview
shows failed calls per model.

**Search or social data failing.** Exa and Bright Data failures are logged and
skipped. A run finishes with less evidence instead of failing. Check the keys
and the providers' status pages.

**Abusive user or runaway spend.** Users → the person → *Suspend* (signs them
out of the API at once and cancels their running work), or lower their daily
limits on the same page. Spend per user is on that page; spend per day and
per model is on the Overview.

**Unexpected spend from monitoring.** Set `MONITOR_ENABLED=false` and restart.
The daily competitor re-checks stop; the "Check for changes" button still works.

**Database.** Schema changes only ever go through Alembic
(`uv run alembic upgrade head`). The API refuses to start if the database is
behind. Never run destructive SQL against the production database.
