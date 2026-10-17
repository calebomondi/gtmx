# Lace: implementation plan

Status: agreed with the owner on 2026-10-18. Supersedes the agent parts of
`docs/v2-architecture.md` (the route-then-answer chat, the discovery DAG and the
separate competitor, account and outreach pipelines). The knowledge base idea
from that doc (§4, facts with sources) is kept and is what Lace stores its
knowledge in.

## 1. What Lace is

A Lace is **one agent per startup**. The founder names it and gives it the
startup's website. The Lace crawls the site, learns what the startup sells and
to whom, and from then on works as the founder's assistant:

- find ideal customers and the contacts to reach them
- understand the competition and monitor it
- spot opportunities: places to showcase (events, awards, press), places to
  sell (tenders, RFPs, procurement), and partners
- draft messages and, with the founder's approval, send them over email,
  LinkedIn, Instagram, TikTok, Facebook and X

Lace replaces every v1 agent workflow with **a single ReAct loop**: the model
thinks, calls a tool, reads the result, and repeats until it can answer. There
is no discovery graph, no specialist team and no separate chat agent.

**Knowledge lives in the database, not in graph state.** The graph state is the
conversation. Everything the Lace learns (facts about the startup, competitors,
accounts, contacts, opportunities, messages) is read and written through tools.

## 2. Decisions

| Topic | Decision |
|---|---|
| Model | Qwen, through `agents/llm`, on models that support tool calling. The fallback ladder, timeouts and usage billing stay. |
| Voice | One voice: the Lace, with the name the founder gave it. The four specialists go. |
| v1 schema | Fresh tables built around a Lace. v1 keeps running on `main` untouched. The useful v1 columns (competitor socials and monitor baselines, account triggers, contact deliverability) are copied on purpose. Pilot workspaces move over in a one-off data migration at cutover; v1 tables are dropped in a later PR. |
| Layering | `agents/lace` declares the tools and the repository **interfaces** it needs. The backend implements them and hands them in when it starts a run. `agents/` never imports `backend/`. |
| Scoping | Every DB tool is bound to one Lace before the model sees it. The model never passes a workspace or Lace id, so it cannot reach another startup's data. |
| Tool shape | Two tiers. **Primitives** (search, scrape, crawl, DB read/write) for ad-hoc work. **Skills** (find competitors, find accounts, find contacts, draft a message, check a competitor) wrap the proven v1 logic, because a raw ReAct loop over search would be slower, costlier and less reliable. |
| Tool results | Typed: `ok`, a short `summary` for the model, `data`, or an `error` the model can reason about. A tool error never crashes the loop. Large output goes to the DB; the model gets the summary. |
| Long work | A tool that takes minutes starts a **job** and returns at once. The job writes to the DB and, when it finishes, wakes the Lace with an event. |
| Sending | Every send, and every paid or outward-facing action, pauses for the founder's approval. Drafting is free. |
| Triggers | One agent, several entry points: a founder message, a schedule (monitoring, opportunity scans, a daily brief), or an event (a reply arrived, a job finished). Each is a new message on the Lace's thread. |

### Channels

Sending a first message to a stranger through official APIs is mostly
restricted. To confirm in Phase 0:

| Channel | Expected |
|---|---|
| Email | Full send and receive through the founder's Gmail or Outlook (OAuth). |
| LinkedIn | Messaging API limited to approved partners. |
| Instagram, Facebook | Messages mostly only in reply to someone who wrote first, inside a time window. |
| X | DMs need a paid API tier, with tight limits. |
| TikTok | No general DM API. |

So every channel goes **draft → approve → send where the API allows it**. Where
it doesn't, the founder gets a one-tap handoff: the message is copied, the
profile opened, and they mark it sent. Third-party providers (unofficial
LinkedIn APIs, connector platforms) are the owner's call, with account-ban risk.

## 3. Phases

Each phase is one or more branches, cut from `feat/v2.0.0`, with PRs into
`feat/v2.0.0`.

### Phase 0: Foundations and spikes
- Qwen tool-calling check: ~20 scripted tasks per candidate model (right tool,
  valid arguments, chaining, knowing when to stop). Pick the main model and a
  backup.
- Tool result contract and the repository interfaces (section 2).
- Channel spike: confirm the table above and pick send or handoff per channel.
- Move Firecrawl and Exa into `data_sources/scraping/`, keys from `Settings`,
  every call bounded by a timeout, with a map/crawl helper.

**Done when:** model, tool contract and channels are decided and written here.

### Phase 1: Data model
- `laces`: name, website, owner `user_id`, status.
- `lace_facts`: topic, claim, source, confidence, origin (crawl, research, user,
  monitor), `valid_as_of`, `superseded_by`. What the Lace knows about the
  startup; a new fact replaces an old one without deleting it.
- `lace_sources`: URL, fetched time, content hash, summary. Raw pages live here,
  not in prompts.
- Entities: competitors, accounts, contacts, opportunities, messages (drafts and
  sent), channel connections.
- Runs: threads, runs, run events, jobs, approvals.

**Done when:** migrations round-trip and `alembic check` is clean.

### Phase 2: The core loop
- `build_lace_graph(checkpointer=..., tools=...)` in `agents/lace`, ReAct, on the
  Postgres checkpointer.
- `agents/llm` gains a tool-calling entry point with the same ladder, timeouts,
  billing and `log_label` as structured calls.
- System prompt: the Lace's identity and rules plus the **startup brief**, read
  from facts every turn (~1k tokens).
- Limits per turn: tool calls, wall clock, tokens. Older turns are summarised so
  a Lace can live for months.
- First tools: `search`, `scrape`, `crawl`, `get_brief`, `get_facts`,
  `record_fact`.

**Done when:** offline tests pass with a stubbed LLM and stubbed tools, and a
live run answers a question about a startup using the tools.

### Phase 3: Onboarding
- Name + URL → map the site → crawl the key pages → extract facts with sources →
  write the brief.
- The Lace shows what it understood and asks the founder to correct it. Edits are
  stored as facts with `origin=user`.
- If the site can't be read, the Lace asks the founder to describe the startup.
- Frontend: "Create your Lace" and the first chat screen.

**Done when:** a founder goes from URL to a confirmed brief in under 3 minutes.

### Phase 4: Chat and the run manager
- A founder message starts a run on the Lace's thread; answers stream over run
  events; runs survive disconnects.
- Job tools return "started"; a finished job posts an event that wakes the Lace.
- Per-user and per-Lace rate limits and concurrent-run caps.

**Done when:** a founder refreshes mid-answer and comes back to the finished one.

### Phase 5: Competitors and monitoring
- `find_competitors`: the core of v1 `get_competitors` (brand-free queries,
  website screening, the substitute gate, profiling).
- `check_competitor`: v1's source-hash change detection.
- Scheduled run: the Lace checks competitors and tells the founder only about
  material changes.

**Done when:** the Lace finds and tracks competitors and reports a real change
unprompted.

### Phase 6: Ideal customers and accounts
- `define_icp`: the Lace reasons over facts and competitors and stores the ICP as
  facts.
- `find_accounts`: the core of v1 `account_discovery` (trigger-first queries,
  recency gate, verification) plus `assess_fit`.

**Done when:** "find me 20 customers in Kenya" returns verified accounts, each
with a trigger and a fit case.

### Phase 7: Contacts
- `find_contacts`: v1 `contacts.py` (site pages, LinkedIn people search, MX
  check) and the socials adapters, across all six channels.

**Done when:** each account has a named person reachable on at least one channel,
or a clear "couldn't find one".

### Phase 8: Outreach on email
- `draft_message`: v1 `gtm_specialist` (research, plan, write, review) plus the
  `grounding` checks.
- `send_message`: creates an approval and pauses the run; sends only on approval.
- Gmail and Outlook OAuth. Replies wake the Lace, which drafts an answer for
  approval.

**Done when:** draft → approve → send → reply → drafted answer works on a real
inbox.

### Phase 9: Social channels
- One adapter per platform under `data_sources/`, send or handoff as decided in
  Phase 0. Inbound messages where the API allows.

**Done when:** the founder reaches a contact on every channel through one
approval flow.

### Phase 10: Opportunities
- Three kinds: **showcase** (events, conferences, awards, podcasts, press),
  **sell** (tenders, RFPs, procurement portals, public "looking for" posts),
  **partner** (companies serving the same buyers, integrations, resellers).
- `find_opportunities`: recency-gated search, stored with deadline, fit and
  source.
- Scheduled scan that skips what was already seen and surfaces only open,
  fitting opportunities.

**Done when:** a weekly scan surfaces real, open opportunities with deadlines.

### Phase 11: The proactive Lace
- A daily brief: what changed, new opportunities, replies waiting, suggested next
  actions.
- The founder sets frequency, quiet hours and channels.

### Phase 12: Cutover
- Admin dashboard views for Laces, runs, jobs and cost.
- Move pilot workspaces into Laces (one-off data migration).
- Retire the v1 pipelines; drop the v1 tables in a later PR.

Phases 0–4 give a Lace that knows the startup and can chat and research. 5–8
bring v1's core value back in one agent. 9–11 are new.

## 4. Risks

| Risk | Mitigation |
|---|---|
| Qwen tool calling is unreliable on long chains | Phase 0 check before building on it; skills keep chains short; the fallback ladder |
| A ReAct loop runs up cost | Per-turn caps on tool calls, time and tokens; daily quotas; paid actions behind approval |
| Context grows with the Lace's age | Brief from facts, tool output trimmed to summaries, older turns summarised |
| Social APIs block cold messages | Handoff path per channel; decided in Phase 0 |
| Accuracy regresses versus v1's tuned pipelines | Skills reuse v1's verification and grounding logic rather than rewriting it |
