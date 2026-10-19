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
  - Cards show what the Lace learned: offer, who it is for, pricing, competitors.
  - Each card has ✓, ✗ and edit; corrections are saved as founder facts.
  - Confirming opens the Lace's workspace.
- **A crawl that fails** (unreachable site, nothing readable) shows the reason and a retry, never a half-printed mascot left hanging.

## 4. The Lace's workspace

- **Three circular buttons** in the floating rail: **mascot** (chat), **Feed** and **Messaging**. On phones the same three sit in a bottom bar.
- **Landing tab:** opening a Lace from the sidebar lands on **Feed**.
- **The mascot button:**
  - idle when the chat is closed
  - alert when the chat is open
  - thinking while the Lace works on a reply
- **Unread counts** show as badges on Feed and Messaging.
- **Today's panels** (facts, competitors, accounts, outreach, inboxes, opportunities, brief) move into these places:
  - Feed: activity and opportunities
  - Messaging: outreach, inboxes and contacts
  - The chat: everything else, as cards
  - A settings sheet: the brief, inboxes and what the Lace knows

## 5. Feed: the notification centre

- **The `lace_activity` table:** `id`, `lace_id`, `kind` (Literal), `title`, `summary`, `ref_type`/`ref_id` (the item it is about), `created_at`, `read_at`.
  - Written in the same transaction as the result it reports.
  - Kept separate from `lace_events`: events are updates queued for the Lace to read, activity is for the founder.
- **What appears:** briefs, opportunities found and closing soon, competitor moves, accounts and contacts found, drafts ready, replies and DMs received, jobs blocked on something the founder can fix.
- **Actions on each item:** Review, Save, Dismiss, Open in chat.
- **"Needs you" strip:** pinned at the top, listing everything waiting on the founder.
- **Funnel line:** accounts, then contacted, replied and meetings.
- **API:**
  - `GET /laces/{id}/activity` (paginated, unread filter)
  - `POST /laces/{id}/activity/read`
  - Polling first; a live stream per Lace can come later.
- **Home Feed** (`/feed`) shows the same items across all of the founder's Laces.

## 6. Messaging

- **Threads:** one inbox for email, X and the Instagram/Facebook DMs, holding drafts, sends, replies and answers. LinkedIn and TikTok show as handoffs (copy, open profile, mark sent). Sending goes through the existing endpoints.
- **Undo send:** a 5-second window to undo before a message goes out.
- **Contacts:** a new `lace_contacts` table (person, title, email, LinkedIn, the account, source, status, timestamps), with indexes on what it is filtered and sorted by.
  - Backfilled from `lace_accounts` key contacts in a separate, idempotent data migration.
  - Contact search writes to it from then on.

## 7. An interactive chat

- **Cards in messages:** the Lace's messages carry UI blocks in `additional_kwargs`, each typed in `agents/schemas/`:
  - choices (buttons)
  - competitor (Track / Dismiss)
  - account (Save / Find contacts / Dismiss)
  - contact (Save)
  - draft (Edit / Send / Discard)
  - opportunity (Save / Not for us)
  - facts to confirm (✓ / ✗ / edit)
- **Choices:** a new `ask_choice` tool lets the Lace offer them. Job results already carry the data the cards need.
- **Clicks:** `POST /laces/{id}/actions` either acts directly (send this draft, save this account) and tells the Lace, or sends the choice back as the founder's reply. The founder rarely has to type.
- **Prompt chips** above the input change with context ("Find 10 buyers in Nairobi", "Draft follow-ups", "What did competitors ship this week?").

## 8. Suggested, then saved

- **The status change:** competitors, accounts, contacts and opportunities gain a `suggested` status and are created with it. Approval makes them `saved`; dismissing keeps today's `dismissed`.
- **What shows where:** Feed, Messaging and Contacts show saved items; suggested ones appear as cards awaiting a decision in the chat and in Feed's "Needs you" strip.
- **Migration:** existing rows become `saved`, so nothing a founder already has disappears.
- **Background jobs** (monitoring, contact search, drafting) run only on saved items.

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
| E | `lace_activity`, its writers and API, the Feed UI and Home Feed |
| F | Messaging: threads, undo send, `lace_contacts` (schema PR, then the backfill PR) |
| G | Interactive chat: UI blocks, `ask_choice`, the actions endpoint, prompt chips |
| H | Suggested, then saved |
| I | The rest of Phase 12: admin views for Laces, runs, jobs and cost; moving pilot workspaces into Laces; retiring v1 |

Each PR goes into `feat/v2.0.0` and is merged on green CI. Moving pilot workspaces in I changes real data, so it waits for the owner's go-ahead.
