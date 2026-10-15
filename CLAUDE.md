# GTMX — Go-To-Market Expert

GTMX researches a product or service end to end. A user signs in, describes an
offer by URL or in their own words, answers a few interview questions, and gets
offer, market, competition and ICP analysis. They then track competitors,
discover target accounts, and run outreach.

- **Agents**: LangGraph pipelines in `agents/`. They are pure: web search, scraping and LLM calls only.
- **Backend**: FastAPI in `backend/app/`. It owns persistence, auth, and running agents.
- **Frontend**: React 19, Vite, Tailwind v4 and shadcn in `frontend/`. This is the customer app.
- **Waitlist page**: React, Vite and Tailwind v4 in `waitlist/`. The public landing page at gtmx.co, with signup and pilot opt-in.
- **Admin dashboard**: a **separate git repository** (Turborepo + Bun, `apps/web` + `packages/ui`) checked out at `admin_dashboard/` and ignored by this repo. It's the internal ops console and follows the same rules and git workflow in its own repo.
- **Identity**: Supabase Auth. **Database**: Postgres (Supabase in prod, Docker locally).

Dependency direction is **frontend / waitlist / admin_dashboard → backend → agents → data_sources/utils**.
All web apps talk only to the backend API. Neither talks to the database or holds a Supabase service key.
Nothing under `agents/` imports `backend/`. Nothing under `data_sources/` imports `agents/`.

---

## Commands

```bash
# Backend (from repo root)
cp .env.example .env                  # first time only, then fill in keys
uv sync                               # install Python deps (incl. dev group)
docker compose up -d --wait           # local Postgres 16 on :5432 (gtmx/gtmx)
scripts/dev.sh                        # starts Postgres if needed, then uvicorn --reload on :8000
uv run ruff check .                   # lint (real-bug rules; runs in CI)
uv run pytest                         # offline tests, on the gtmx_test Postgres DB (auto-created + migrated)
uv run pytest -m live                 # tests that hit real LLM/search APIs (opt-in)
uv run alembic upgrade head           # apply migrations
uv run alembic revision --autogenerate -m "add_x_to_y"

# Frontend (from frontend/). Bun is the only JS package manager in every app.
bun install
bun run dev                           # Vite on :5173, proxies /api (incl. WS) to :8000
bun run build                         # tsc -b && vite build. Must pass before any PR.
bun run lint                          # oxlint

# Waitlist page (from waitlist/)
bun install && bun run dev           # Vite on :5174, proxies /api to :8000
bun run build && bun run lint

# Admin dashboard (from admin_dashboard/)
bun install
bun run dev                           # turbo dev (apps/web)
bun run build && bun run typecheck && bun run lint
```

---

## Git workflow (mandatory)

1. **Never commit to `main` or `dev` directly.** Every change goes on its own branch cut from the latest `dev`.
2. Branch names are `<type>/<short-kebab-summary>`. Types are `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `db`.
3. One concern per branch and PR. Don't mix a refactor with a feature or a migration with unrelated UI.
4. Open the PR **into `dev`** with `gh pr create --base dev`. The body covers what changed, why, how it was tested, and any migration or env changes.
5. **Never merge your own PR.** The owner reviews and merges. `dev` is promoted to `main` for release.
6. Commit messages are imperative and specific ("Enforce workspace ownership on competitor routes"), not "fix stuff".
7. Before opening a PR, all of these pass for every app the PR touches: `uv run ruff check .`, `uv run pytest`, `bun run build` and `bun run lint` (frontend), `bun run build`, `typecheck` and `lint` (admin_dashboard), and `alembic upgrade head` on an empty database.
8. Use **Bun only** for JavaScript (`bun install`, `bun run`, `bunx`). Never add a `package-lock.json`, `yarn.lock` or `pnpm-lock.yaml`.
9. Never commit `.env*` (except `.env.example`), `*.db`, `node_modules/`, `dist/`, `agents/.cache/`, or test `_out/` artifacts.

---

## File structure rules

```
agents/
  pipelines/<feature>/      # one LangGraph graph per module: build_<x>_graph()
  schemas/                  # ALL pydantic state/IO models for agents (single source)
  llm/                      # LLM client, provider ladder, retries
  prompts/                  # long prompt templates, when they outgrow their node file
  runtime.py                # top-level discovery graph wiring only
backend/app/
  api/v1/endpoints/<resource>.py   # thin HTTP layer: validate, authorize, call service
  api/deps.py               # auth + ownership dependencies (the ONLY place they live)
  services/<resource>.py    # business logic + DB access. No FastAPI imports.
  runs/                     # run manager: background agent execution + event log
  database/models.py        # SQLAlchemy models
  database/migrations/      # Alembic
  schemas/<resource>.py     # pydantic request/response models
data_sources/               # external API adapters (Exa, BrightData, parsers)
config.py                   # Settings: the ONLY place env vars / .env are read (all layers)
frontend/src/
  features/<feature>/       # components, types, store for one feature
  components/ui/            # shadcn primitives. Generated, so don't hand-edit for features.
  components/               # shared, feature-agnostic components
  lib/api/                  # typed API client, one module per backend resource
  lib/                      # cross-cutting utilities (auth, supabase, utils)
admin_dashboard/
  apps/web/src/features/<feature>/   # same feature-folder rule as frontend/
  apps/web/src/lib/api/              # typed client for /api/v1/admin/*
  packages/ui/                       # admin's shadcn primitives
```

- **One home per concept.** Before creating a file, search for an existing one that owns the concept. A new top-level directory needs a reason in the PR.
- **Feature code lives with its feature.** A component used by only one feature goes in that feature's folder. Promote it to `components/` only when a second feature needs it.
- **Python modules are `snake_case.py`.** Frontend files are `kebab-case.tsx`. React components are `PascalCase`.
- **Keep files small.** Over ~600 lines (Python) or ~400 lines (TSX) is a signal to split by responsibility, not to add another section header.
- **No orphans.** Don't keep an empty file, a commented-out module, a `_old`/`_v2`/`2.py` copy, a stray notebook output, or a root-level scratch script. Delete dead code; git remembers it.
- **Notebooks** (`agents/notebooks/`) are for exploration only. Production code never imports from them, and outputs are cleared before commit.
- **Tests mirror the source tree:** `backend/tests/...` and `agents/tests/...`. Fixtures go in `conftest.py`, not copy-pasted setup.

---

## Code-smell rules

Treat each of these as a review blocker:

- **Silent failure.** `except Exception: pass`, or returning `""`/`None` for a hard error the caller can't tell apart from "no data". Catch narrowly, log with context (`logger.exception`), and raise or return a typed result.
- **Missing authorization.** Any route that touches a workspace, project, competitor, account or run without going through the ownership dependency in `api/deps.py`.
- **Env reads outside settings.** `os.environ`/`getenv`/`load_dotenv` anywhere except root `config.py` (add a field to `Settings` instead), or `import.meta.env` outside `lib/` (frontend).
- **Dialect-specific code in shared paths.** SQLite-only `connect_args`, raw SQL that only works on one database, or `ALTER TABLE` in app startup.
- **Blocking the event loop.** Calling sync LLM/HTTP/graph `.invoke()` inside an `async def` without `asyncio.to_thread`, or `time.sleep` in async code.
- **Unbounded work.** Every LLM, search and scrape call has a timeout. Every list endpoint has a limit. Every agent run has a wall-clock cap.
- **Magic values.** Model names, limits, URLs and timeouts go in settings or a named constant, not inline.
- **God functions.** A function over ~60 lines, or one that both orchestrates and does I/O and formats output, gets split.
- **Boolean-flag parameters** that switch a function between two behaviours. Write two functions.
- **Stringly-typed state.** Phase names, run statuses and offer types are `Enum`/`Literal` (backend) and union types (frontend), never free strings compared in many places.
- **Mock data in shipped paths.** A mock is allowed only behind an explicit `isMock`/feature flag that renders a visible "Preview" label.
- **`any` in TypeScript,** non-null assertions (`!`) without a comment saying why, and `// @ts-ignore`.
- **Comments.** They explain *why*, not *what*. A comment that restates the code, or narrates history ("this used to..."), should go. Keep the reasoning and drop the changelog.
- **`print()` for diagnostics.** Use `utils.log.logger` (backend/agents). Never leave `console.log` in the frontend.

---

## Don't Repeat Yourself rules

- **One source of truth per schema.** Agent state models live only in `agents/schemas/`. API shapes live only in `backend/app/schemas/`. Frontend types mirror the API in `lib/api/` and are imported from there, never redeclared in a feature.
- **Before writing a helper, search for it.** Before adding a function, `grep` for one that already exists, especially in `agents/helpers.py`, `utils/`, `frontend/src/lib/`. Extend it; don't fork a near-copy.
- **Rule of two.** The second time logic is copied, extract it. This covers shared prompt fragments, serialization of the offer snapshot, fetch-and-404 lookups, store boilerplate, and error-to-message mapping.
- **One way to do each cross-cutting thing:**
  - DB session: `Depends(get_db)` in routes, `AsyncSessionLocal()` only in the run manager.
  - Ownership lookup: `get_owned_workspace()` / `get_owned_project()` from `api/deps.py`.
  - LLM call: `agents/llm` (never instantiate a chat model directly in a node).
  - Web search/scrape: `data_sources/scraping` (never call Exa directly from an agent).
  - Frontend HTTP: `apiFetch` in `lib/api` (never bare `fetch` in a component).
  - Frontend shared state: the `useSyncExternalStore` store pattern in `lib/*-store.ts`. Copy the pattern from an existing store; don't invent a new state library.
- **Don't duplicate config.** Ports, origins, model ids and limits are defined once and imported.
- **Generated code isn't duplication.** shadcn `components/ui/*` is generated and fine to leave alone, but never copy one to make a variant. Wrap it instead.

---

## Database & migration rules

- **Alembic is the only way the schema changes.** `Base.metadata.create_all` and `ALTER TABLE` in app startup are forbidden. The app must refuse to start if the database is not at `alembic heads`.
- **Postgres everywhere.** Local dev uses Postgres (Docker), the same as prod. SQLite is not supported for the app or the LangGraph checkpointer.
- **Every model change ships a migration in the same PR.** Use autogenerate, then **read and hand-edit** the result. Autogenerate misses renames, server defaults, enum changes and data moves.
- **Never edit a migration that has been merged to `dev`.** Fix forward with a new migration.
- **Every migration has a working `downgrade()`.** Before the PR, run `upgrade head`, then `downgrade -1`, then `upgrade head` on a fresh database.
- **Migration file name:** `YYYYMMDD_HHMM_<short_description>.py` with a descriptive message (`add_notes_to_competitors`).
- **Zero-downtime shape (expand → migrate → contract):**
  - Add columns as nullable or with a `server_default`. Never add a `NOT NULL` column without a default to a populated table.
  - Renames and type changes take three PRs: add the new column, backfill and dual-write, then drop the old column after the code no longer reads it.
  - Never drop a column or table in the same PR that stops using it.
- **Data migrations** (backfills) are separate migration files from schema migrations and must be idempotent.
- **Constraints belong in the database,** not only in code: FKs with an explicit `ondelete`, unique constraints for natural keys, `NOT NULL` where the domain requires it, and indexes on every FK and every column used in a `WHERE` or `ORDER BY`.
- **No FK to tables we don't own.** Supabase owns users, so `user_id` columns are indexed UUIDs with **no** FK to a local `users` table.
- **Timestamps** are `DateTime(timezone=True)` and stored in UTC.
- **JSON columns** are for opaque agent output blobs only. Anything we filter, sort or join on gets a real column.
- **Never run destructive SQL against a shared database** (`DROP`, `TRUNCATE`, unscoped `DELETE`) without the owner's explicit OK.

---

## Backend rules

- Endpoints stay thin: parse → authorize → call a service → return a response model. Every route declares `response_model`.
- Every resource route depends on the authenticated user. Every workspace-scoped route resolves the workspace through the ownership dependency, which returns 404 (not 403) for someone else's resource.
- Agent runs never live inside a request or a WebSocket handler. They're started by the run manager, persisted as a run row plus an event log, and survive client disconnects. WebSockets/SSE only *subscribe* to a run's events.
- Long-running agent work is cancellable and has a wall-clock timeout. Failures are recorded on the run row with a user-facing message.
- Per-user rate limits and concurrent-run caps are enforced before a run starts.

## Agent rules

- Each pipeline exposes `build_<name>_graph(checkpointer=...)` and is unit-testable with a stubbed LLM and stubbed search.
- Nodes return only the state keys they own. Parallel branches must write disjoint keys.
- All LLM access goes through `agents/llm` with a `log_label`. Structured output uses pydantic models from `agents/schemas/`.
- Prompts never contain secrets or other users' data. Scraped content is treated as untrusted input.
- Any pydantic model that can reach a checkpoint must live in a module registered with the checkpointer serializer.

## Frontend rules

- Server data goes through `lib/api` with typed responses. Loading, empty and error states are handled for every async view.
- No inline business logic in JSX. Derive it in a hook or store.
- Routes are declared only in `App.tsx`. Auth-gated routes go through the auth layout.
- Use Tailwind tokens and shadcn variants, not one-off hex colors or inline styles.

---

## Admin dashboard rules

- Every admin endpoint lives under `/api/v1/admin/*` in `backend/app/api/v1/endpoints/admin/`. It's guarded by `require_admin` from `api/deps.py`, which checks the Supabase `app_metadata.role == "admin"` claim. A UI-side check alone is never enough.
- Admins are bootstrapped from `ADMIN_BOOTSTRAP_EMAILS` at startup (idempotent). After that, admins grant or revoke the role from the dashboard through an audited endpoint. An admin can't revoke their own role, and the last admin can't be removed.
- Admin endpoints are read-mostly. Every admin write (suspend a user, cancel a run, change a quota) goes through a service function and writes an `admin_audit_log` row recording who, what, when, and the before and after values.
- No mock data ships. The template's `data.json` and placeholder nav items are deleted, not hidden.
- Admin and customer app don't import each other's code. If both need the same API types, the backend's OpenAPI schema is the shared contract.
- Paginate every list (users, runs, workspaces). Never fetch an unbounded table into the browser.

---

## Definition of done

A change is done when:

- It works end to end locally (backend, plus the frontend and/or admin dashboard, against real Postgres).
- Tests cover the new behaviour.
- Every check from Git workflow rule 7 is green for the apps it touches.
- Migrations round-trip.
- No new smell from the list above is introduced.
- It's on its own branch with a PR into `dev`, waiting for the owner's review.
