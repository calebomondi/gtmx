# Lace UI: the founder's experience

Status: agreed with the owner on 2026-10-19. Phase 12 of docs/lace-plan.md,
reshaped. The chat with a Lace is the main way a founder works with it; Feed
and Messaging hold what it finds and does. Implementation starts with PR A.

## Decisions

| Question | Decision |
|---|---|
| Sidebar group name | **Crew** (was "Campaigns") |
| Mascot state in the sidebar | Real status first; the owner's position rule as the fallback |
| v1 sidebar items | Home Feed becomes the feed for every Lace; Projects is removed; Search covers every Lace |
| Approve before saving | Yes. Research results start as *suggested*, and the founder's approval makes them *saved*. This replaces today's auto-save. |
| `Lace.tsx` mascot | Committed in PR A as `components/lace-mascot.tsx` (kebab-case) |

## 1. Sidebar

- **"New Workspace" becomes "New Lace"**, which opens `/new`. The v1 workspace form is retired.
- **Extras loses its "Laces" entry.** It keeps Accounts (connected accounts) and Archive, which now holds archived Laces.
- **The Crew group** lists Pinned first, then all Laces. Each row shows a small mascot and the Lace's name. Below 24px the mascot draws its simplified face.
- **Pinning:** a new `laces.pinned` column (migration), and `lib/laces-store.ts` following the `useSyncExternalStore` store pattern.
- **Ordering:** by latest activity, so the Laces that need attention sit at the top.

### Mascot state

Each Lace in the list carries a `mood` from the backend when something is
actually going on:

| Mood | When |
|---|---|
| thinking | A conversation turn or a background job is unfinished |
| alert | Something waits on the founder: an outreach draft to send, or a reply or DM not yet read |

With no mood, the owner's rule applies:
- Pinned rows are alert.
- In Laces, the first row is alert, the second idle, and the rest sleepy.

The list is ordered by latest activity (the Lace's newest run), so the
position rule follows recency too. The list response carries `mood` and
`last_active_at`, so the sidebar makes no per-Lace calls. It refreshes every
30 seconds. PR E adds unread activity to alert.

## 2. `/new`: name and website

- **The form:** a name and the startup's website, then **Create My Lace**. The browser's timezone is sent, as it is today.
- **The mascot watches the founder.**
  - `Lace` gets a `lookAt` prop: one pointer listener per page, throttled to animation frames, moving the eyes about ±8 viewBox units toward the cursor while the blink continues.
  - It is off when the user prefers reduced motion.
- **Focus:** while a field has focus, the eyes look at that field.
- **Its name:** typing the name gives a brief "alert" pop, as if the Lace heard its name for the first time.

## 3. Creation: the mascot is 3D-printed

- **The print effect:**
  - A clip mask reveals the mascot from the bottom up in layers.
  - A bright nozzle line moves across the current layer, and the part not yet printed shows faint layer lines.
  - When printing finishes, the eyes open with a blink into alert.
- **The progress is real, not a timer.** Onboarding emits a new `progress` frame (0–1) alongside its step frames:

  | Stage | Progress |
  |---|---|
  | Mapping the site | 0–0.15 |
  | Reading pages (per page done) | 0.15–0.70 |
  | Extracting facts | 0.70–0.90 |
  | Writing the opening message | 0.90–1.0 |

- **The step line under the mascot** ("Reading /pricing…") stays as it is.
- **Confirm:**
  - Cards show what the Lace learned, grouped: what you sell, who buys, who it is for, pricing, how you stand out.
  - Each fact has ✓ (`confirmed_at`), ✎ (the founder's wording supersedes it as a `user` fact) and ✗ (`retracted_at`: it leaves what the Lace knows but stays on record).
  - "Looks right, meet {name}" opens the Lace.
- **A site that can't be read:** the page says so and offers "Tell {name}". That goes to the chat, where the Lace has already asked the founder to describe the startup. A retry would mostly hit the same unreadable site.
- **A run that fails:** shows the reason, "Start again" (`/new`) and "Open {name}".
- **Route:** `/lace/:id/setup?run=…`. Without `run`, it finds the active onboarding run, or goes straight to review once onboarding has finished.

## 4. The Lace's workspace

- **Three circular buttons** in the floating rail: **mascot** (chat), **Feed** and **Messaging**. On phones the same three sit in a bottom bar.
- **Landing tab:** opening a Lace from the sidebar lands on **Feed**.
- **The mascot button:**
  - idle when the chat is closed
  - alert when the chat is open
  - thinking while the Lace works on a reply
- **Unread counts** show as badges on Feed and Messaging.
- **Routes:** `/lace/:id/feed|chat|messaging`; `/lace/:id` opens Feed. Creation's "meet {name}" opens the chat, where the first message waits.
- **Where today's panels went** (PR D):
  - Feed: opportunities, target accounts and competitors, as Cards. PR E puts the activity feed above them.
  - Messaging: outreach and inboxes. PR F adds threads and contacts.
  - Settings sheet (header button): the brief and what the Lace knows.
- **The rail:** one load of the Lace serves all three tabs, so a running reply keeps streaming while the founder is on Feed.

## 5. Feed: the notification centre

- **The `lace_activity` table:** `id`, `lace_id`, `kind` (Literal), `title`, `summary`, `ref_type`/`ref_id` (a reply or a brief), `created_at`, `read_at`.
  - Written in the same transaction as the result it reports, beside the update each job queues for the Lace.
  - Kept separate from `lace_events`: events are updates queued for the Lace to read, activity is for the founder.
- **What appears:** briefs, new competitors, competitor moves, new target accounts, contacts found, drafts ready, each reply received, new opportunities, and searches that failed (with the reason).
- **Each item's action** opens where it leads: Messaging, the chat, or a Feed section.
- **"Needs you" strip:** messages waiting (drafts to send, replies not yet read) and searches that stopped for the founder's input.
- **Unread:** opening Feed marks everything read; what was new keeps a dot for the rest of the visit. Unread items badge the Feed button and turn the sidebar mascot alert.
- **API:**
  - `GET /laces/{id}/activity` (newest first, `before` pages back)
  - `POST /laces/{id}/activity/read`
  - Polled every 30 seconds.
- **E2:**
  - Home (`/feed`, where login lands) shows activity across all the founder's Laces (`GET /laces/activity`), each item labelled with its Lace and opening there. A "Needs you" row lists the Laces whose mood is alert.
  - Each Lace's Feed gets the funnel line (`GET /laces/{id}/funnel`): target accounts, then contacted (a message sent), replied, and interested (keen, or asking to meet), counting distinct accounts.
  - The v1 workspace feed moves to `/workspace-feed` until PR I.

## 6. Messaging

- **Conversations (F3):** the Lace's outreach grouped into conversations by `thread_id`, else by channel and recipient. On wider screens, the list (the ones that need the founder first) sits beside the open conversation. On phones, the list opens into one conversation with a back button.
  - Sent messages and replies show as bubbles; replies carry how they were read (asked a question, wants to meet, …).
  - Drafts sit at the bottom of their conversation, editable, using the same send and handoff rules as before (email, X, and Instagram or Facebook answers are sent from here; LinkedIn and TikTok are copied, sent there and marked sent).
- **Undo send (F3):** Send counts down 5 seconds with an Undo button. Leaving the Lace mid-countdown sends at once.
- **Contacts (F1, F2):** `lace_contacts`, one row per person per Lace, keyed by email, else LinkedIn, else name. Synced by account and contact searches, and backfilled from account records by an idempotent data migration. Messaging lists them in a searchable table.

## 7. An interactive chat

- **Blocks** (`agents/schemas/lace_ui.py`): a reply can carry `choices` (a question with 2–5 answers) and `card`s (a snapshot of a saved competitor, account, opportunity or draft).
- **Tools:**
  - `ask_choice(question, options)`
  - `show(kind, ids)`: up to 6 cards, drawn only from saved items (`agents/lace/cards.py`)

  The system prompt tells the Lace to show items instead of listing them, and to offer choices when the next step is one.
- **Kept with the reply:** a turn's blocks are attached to its final reply in the checkpoint (`additional_kwargs.ui`), so they show whenever the conversation is read. `GET /messages` returns `ui` only on replies that have some.
- **Card actions act on the item as it is now:**
  - competitor: Open, Not a competitor
  - account: Find contacts (or Look again), Dismiss. Uses `POST /laces/{id}/accounts/{aid}/find-contacts`, the one new endpoint.
  - opportunity: Open, Not for us
  - draft: Review in Messaging, or Send with the 5-second undo

  A card shows Dismissed, Sent or Discarded once that has happened.
- **Choices:** a click sends the option as the founder's message, only on the latest reply while the Lace is free.
- **Prompt chips:** above the input, from where the work stands (the next pipeline step first, then standing questions), in one row.
- **Not done:** a direct action does not tell the Lace (it reads current state with its list tools anyway), and the fact-confirm card stays on the creation page.

## 8. Suggested, then saved

- **H1 (competitors, accounts, opportunities):** what a search finds is inserted as `suggested`. The founder saves it (tracked, target, open) or dismisses it. Items already on file keep their status, so everything from before counts as saved and a dismissal still sticks.
- **Worked from only once saved:**
  - The store's `competitors()`, `accounts()` and `opportunities()` stay saved-only, so the ICP, drafting, contact search and monitoring use only what the founder approved.
  - `suggestions()` and the `list_suggestions` tool let the Lace put new finds in front of the founder as cards (`show` finds suggested items too).
  - The prompt and the job updates say so.
- **Where the founder decides:**
  - A "To review" list at the top of each Feed section, with Save (Track for competitors) and Dismiss.
  - Save and Dismiss on chat cards.
  - Suggestions count in "Needs you", turn the sidebar mascot alert, and appear in the brief ("waiting for the founder").
- **API:** list endpoints take `status=suggested`. The update requests accept only saved or dismissed values.
- **Migration:** only the CHECK constraints change. A downgrade turns suggestions into saved items.
- **H2 (contacts), as the owner chose on 2026-10-19:**
  - People found at saved accounts go into Contacts automatically.
  - Outreach is drafted only to people the founder approved (`lace_contacts.approved_at`), one by one or everyone at an account in one click (in Contacts, or on the account's chat card).
  - An account whose people all wait for approval isn't drafted to; it's reported as waiting, rather than falling back to its own pages. An account with no people can still be reached through its own pages.
  - Contacts on file before this start unapproved.
  - People waiting for approval count in "Needs you".

## 9. Also

- **Browser notifications:** opt-in, for replies and DMs.
- **Search** (Ctrl K) covers every Lace's facts, contacts, threads and opportunities.

## PRs, in order

| PR | Scope |
|---|---|
| A | Mascot into the codebase, the sidebar restructure (Crew, New Lace, Extras), `laces.pinned`, `laces-store`, status in the Lace list |
| B | `/new` with eye tracking |
| C | Creation page: `progress` frames, the print effect, confirm cards |
| D | Workspace shell: three buttons, mascot states, Feed as the landing tab, panels re-homed |
| E1 | `lace_activity`, its writers and API, the Lace's Feed (Needs you, Activity, unread badges) |
| E2 | Home Feed across every Lace, and the funnel line |
| F | Messaging: threads, undo send, `lace_contacts` (schema PR, then the backfill PR) |
| G | Interactive chat: UI blocks, `ask_choice`, the actions endpoint, prompt chips |
| H | Suggested, then saved |
| I | The rest of Phase 12: admin views for Laces, runs, jobs and cost; moving pilot workspaces into Laces; retiring v1 |

### PR I progress

- **Admin views:** gtmx #189 (API) is merged. gtmx-admin #16 (pages) is open, to merge when v2 reaches production, since the console deploys from `main`.
- **Pilot migration:** `scripts/migrate_pilots.py` over `services/pilot_migration.py`.
  - A dry run by default; `--apply` writes. `--user-id` limits it to one founder. Idempotent.
  - One Lace per founder per site, matched by domain key.
  - Carried: the offer profile as facts; competitors (tracked, with their monitoring baseline); accounts (with their review status; those without a trigger stay behind); contacts (unapproved); outreach that went out or came in.
  - Not carried: drafts, v1 chat, signals.
  - The owner runs it: first the dry run, then `--apply`.

- **Retiring v1, frontend:** the v1 pages, routes, stores, components and API modules are gone. The app is Home, New Lace, the Laces and connected Accounts. Search (Ctrl K) and Archive went with them, since both only covered v1 workspaces; search returns as search across Laces in its own PR.
- **Retiring v1, backend:** the v1 API routes, run kinds and sweeps, and the agent pipelines a Lace doesn't reuse. The v1 tables stay until the pilots are moved, then are dropped in their own PR.

Each PR goes into `feat/v2.0.0` and is merged on green CI. Moving pilot workspaces in I changes real data, so it waits for the owner's go-ahead.
