# GTMX launch plan

**Target:** live on 2026-10-15 for up to 50 users, with every feature shipped. Testing is local for now; hosting is out of scope.
**Process:** each item below is one branch and one PR into `dev`. The owner reviews and merges. A phase starts after the previous phase's blocking PRs are merged; the "Depends on" column says which.

---

## Feature inventory: where each feature really stands

| Feature | Frontend | Backend / agent | Status |
|---|---|---|---|
| Auth (login, signup, reset, callback) | ✅ | ✅ Supabase | Works |
| Projects (CRUD, reorder, archive) | ✅ | ✅ | Works. Fresh DB boot is broken (FK to `users`) |
| Workspaces (view, rename, pin, archive, delete) | ✅ | ⚠️ no ownership check | Security hole |
| Discovery run (interview, stepper, chain of thought) | ✅ | ⚠️ run tied to the WebSocket | A disconnect kills the run |
| Insights tabs (offer, market, competition, ICP, specialists) | ✅ | ✅ | Works |
| Competitors (agent run, manual add, notes, delete) | ✅ | ⚠️ no auth, BackgroundTasks | Security hole, runs lost on restart |
| Account discovery | ⚠️ UI exists, not wired into `lib/api` | ⚠️ no auth | Needs wiring |
| Feeds (home and workspace signals) | ✅ UI | ❌ in-memory browser store only | Needs a backend |
| Agent chat (per workspace) | ✅ UI shell | ❌ `chat_agent.py` is empty | Needs building |
| Connected accounts (Composio) | ✅ UI on mock data | ❌ stub script | Needs building |
| Outreach (drafts, send, inbox) | ✅ UI shell (854 lines) | ❌ `reach_out_agent.py` is empty | Needs building |
| Monitoring (competitor change watch) | n/a | ❌ `monitor_agent.py` is empty | Needs building |
| Socials (competitor social presence) | ❌ 10-line stub | ⚠️ BrightData adapter only | Needs building |
| Admin dashboard | ⚠️ template + mock `data.json` | ❌ no admin API | Needs building |

---

## Phase 1 — Platform foundation (Day 1, Oct 11)

Everything else builds on this phase.

| # | Branch | What | Done when | Depends on |
|---|---|---|---|---|
| 1.1 | `chore/local-postgres` | `docker-compose.yml` with Postgres 16, `.env.example` for every app, and `scripts/dev.sh` boots against it | `docker compose up -d && scripts/dev.sh` gives a green `/health` | — |
| 1.2 | `db/alembic-baseline` | Add Alembic and a baseline migration from the current models. Drop the `users` FK (`user_id` becomes an indexed UUID). Delete `create_all` and the `_ensure_*` ALTERs. Startup refuses a DB not at head | `alembic upgrade head` on an empty DB, then a round-trip, then the app boots | 1.1 |
| 1.3 | `refactor/settings-single-source` | Merge `config.py` and `backend/app/config/settings.py` into one pydantic `Settings`. Model ids, limits and timeouts become settings | `grep environ` finds hits only in settings | 1.2 |
| 1.4 | `refactor/postgres-checkpointer` | `AsyncPostgresSaver` replaces SQLite. Engine options become dialect-aware | A discovery run checkpoints to Postgres | 1.2 |
| 1.5 | `test/repair-suite` | pytest dev group, `conftest` with a stub LLM and stub search, `live` marker, legacy-import tests fixed or deleted | `uv run pytest` is green and needs no network | 1.3 |
| 1.6 | `chore/ci` | GitHub Actions: pytest + Postgres service, alembic round-trip, frontend build and lint, admin build, typecheck and lint | CI is green on PRs into `dev` | 1.5 |
| 1.7 | `chore/admin-repo-setup` | Admin stays a **separate repo**: push it to its own GitHub remote with a `dev` branch and the same PR flow. `admin_dashboard/` is ignored here. Bun everywhere: the frontend drops `package-lock.json` | Both repos build with `bun run build` | — |

## Phase 2 — Structure cleanup (Day 1–2)

Mechanical moves with no behaviour change. This phase runs early so feature work lands in the final layout and doesn't conflict with the moves.

| # | Branch | What |
|---|---|---|
| 2.1 | `refactor/agent-schemas` | Merge `agents/states.py` and `sub_agents/schema_states.py` (now `pipelines/schema_states.py`) into `agents/schemas/`. Update the checkpointer allowlist |
| 2.2 | `refactor/remove-legacy-agents` | Move `gather_context` out of `sub_graphs/`, then delete `sub_graphs/`, root `llm/`, `main.py`, `sql/`, `test_product.docx`, stale notebooks and `_check_competitors.py`. Rename `sub_agents/` to `pipelines/` |
| 2.3 | `refactor/backend-services` | Pull business logic out of the endpoints into `services/`. Endpoints become thin |
| 2.4 | `refactor/frontend-features` | Move to the `src/features/<x>/` layout. Split `lib/api.ts` into `lib/api/<resource>.ts`. Remove the empty files (`canvas.tsx`, `chat-containter.tsx`) and unused shadcn-studio examples. Use a single lockfile |

## Phase 3 — Security & limits (Day 2, Oct 12)

| # | Branch | What | Done when |
|---|---|---|---|
| 3.1 | `fix/ownership-enforcement` | Add `get_owned_workspace` and `get_owned_project` deps and apply them to **every** workspace, competitor, account and insights route. Someone else's resource returns 404 | A test proves user B gets 404 on every one of user A's routes |
| 3.2 | `feat/admin-auth` | `require_admin` (Supabase `app_metadata.role`) plus an `admin_audit_log` table | A non-admin gets 403 on `/api/v1/admin/*` |
| 3.3 | `feat/usage-limits` | Per-user caps: concurrent runs (1 discovery, 2 background), runs per day, request rate limit. Limits are settings | Going over a cap returns 429 with a clear message |

## Phase 4 — Reliable agent runs (Day 2–3)

This is the most important phase for avoiding visible glitches.

| # | Branch | What | Done when |
|---|---|---|---|
| 4.1 | `feat/run-manager` | `runs` and `run_events` tables. Runs execute as tasks owned by the server, not by the socket. They have a wall-clock timeout and can be cancelled. On boot, orphaned runs are marked failed | Killing the browser mid-run doesn't stop the run |
| 4.2 | `feat/discovery-on-run-manager` | The discovery WebSocket only subscribes: it replays `run_events` from a cursor, then follows live. Interview answers are posted to the run. The frontend reconnects with backoff and resumes | Refresh mid-interview, then reconnect, and the run continues where it was |
| 4.3 | `refactor/background-runs-unified` | Competitor and account runs move onto the run manager, with polling replaced by the same event stream | One code path for all agent runs |
| 4.4 | `feat/llm-resilience` | Per-call timeout, a fallback provider (OpenRouter is already wired), and token and cost accounting per run saved on the run row | A forced DashScope failure still lets the run finish |

## Phase 5 — Complete the features (Day 3–4, Oct 13–14)

| # | Branch | What | Done when |
|---|---|---|---|
| 5.1 | `feat/accounts-ui-wiring` | Typed account API client. Wire the outreach accounts list, run trigger and status edits | Discovered accounts show up and can be triaged |
| 5.2 | `feat/signals-feed` | `signals` table. Signals are emitted by runs (discovery finished, new competitor, new accounts, monitor changes). `GET /signals` (home) and `GET /workspaces/{id}/signals`. The feeds are backed by the API | Feeds survive a refresh and show real events |
| 5.3 | `feat/workspace-chat` | Chat agent scoped to a workspace. It is grounded in the persisted insights, competitors and accounts, with a web-search tool. Streams over the run event channel. `chat_messages` table | Ask "who are my top 3 competitors and why?" and get an answer that cites the workspace data |
| 5.4 | `feat/composio-connections` | `connections` table. Composio OAuth connect, callback and disconnect for **Gmail, LinkedIn, Instagram, TikTok and X**. Mock connections removed | A user connects each channel and the status is real |
| 5.5 | `feat/outreach-agent` | Reach-out agent drafts personalised messages per account from the ICP and insights: email via Gmail, plus DMs and posts on the connected socials wherever Composio exposes the action. The user reviews and edits, then sends. `outreach_messages` table with status. **Nothing sends without an explicit user click** | Draft → edit → send works end to end with a real mailbox |
| 5.6 | `feat/competitor-monitor` | Monitor agent re-checks tracked competitors (pricing, features, news) on a schedule (an APScheduler job inside the single backend instance) and emits diff signals. There's also a "check now" button | A changed competitor page produces a feed signal |
| 5.7 | `feat/competitor-socials` | BrightData social profiles (LinkedIn, X, Instagram, TikTok) added to competitor profiles, plus a socials tab. **Key verified 2026-10-10: all four platforms return data.** Scrapes take 13–56s each, so they run as background runs, never inline | A competitor card shows real social stats |

**If we fall behind,** these are the agreed cuts:
- 5.5 ships draft and copy only, with no send.
- 5.6 ships manual "check now" only, with no schedule.
- 5.7 ships LinkedIn only.

The owner decides on Day 3 evening.

## Phase 6 — Admin dashboard (Day 3–4, in parallel with Phase 5)

| # | Branch | What |
|---|---|---|
| 6.1 | `feat/admin-api-overview` | `/admin/metrics`: users, active users, runs by status, success rate, average duration, LLM and search cost per day |
| 6.2 | `feat/admin-api-entities` | Paginated users (Supabase admin API), workspaces, runs with event timelines, and signals |
| 6.3 | `feat/admin-api-actions` | Suspend or reactivate a user, cancel a run, adjust a user's quota, **grant or revoke admin**. All of these write to the audit log. `ADMIN_BOOTSTRAP_EMAILS=kalebmokua@gmail.com` seeds the first admin. Self-revoke and removing the last admin are blocked |
| 6.4 | `feat/admin-ui` | Replace the template: Supabase login with an admin gate, an overview with charts, users, runs (with live timeline), workspaces, and the audit log. `data.json` deleted |

## Phase 7 — Hardening & release (Day 5, Oct 15)

| # | Branch | What |
|---|---|---|
| 7.1 | `chore/observability` | Structured JSON logs with run_id and user_id, Sentry (backend plus both frontends), LangSmith tracing |
| 7.2 | `test/e2e-smoke` | Playwright smoke test: signup → discovery → insights → competitors → accounts → draft outreach → admin sees the run |
| 7.3 | `test/load` | 10 concurrent discovery runs locally. Check the thread pool, DB pool and provider rate limits; tune the settings |
| 7.4 | `fix/qa-sweep` | Bugs found while driving every screen: loading, empty and error states, plus a pass over dark mode and mobile |
| 7.5 | `docs/runbook` | README with setup, env vars, how to run each app, how to grant admin, and incident steps |
| — | release PR `dev` → `main` | Done after the owner signs off |

---

## Risks

1. **Scope.** Phase 5 builds four new agents (chat, outreach, monitor, socials) in two days. The cut lines above are the release valve.
2. **Provider limits.** At 50 users, concurrent runs hit DashScope rate limits and Exa quotas. 3.3 caps it and 4.4 adds a fallback.
3. **Phase 4 is the largest change.** It's isolated behind the run manager, so if 4.2 slips we can keep the WebSocket-owned run and add checkpoint resume as a stopgap.
4. **Sending email for users** carries reputation and abuse risk. Sending is always user-initiated, rate-limited, and logged.

## Owner decisions (resolved 2026-10-10)

- [x] Plan approved
- [x] Admin dashboard stays a separate repo
- [x] Composio account exists. Channels: Gmail, LinkedIn, Instagram, TikTok, X
- [x] BrightData key valid. LinkedIn, X, Instagram and TikTok scrapers all verified live
- [x] First admin is kalebmokua@gmail.com. Admins can grant admin to others
- [x] Bun everywhere
