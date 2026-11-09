# GTM skills: making each Lace a pro at go-to-market

Status: agreed with the owner on 2026-11-08. Build order: Phase 0, then
1 → 2 → 4 → 3 → 5.

## Why

The owner came back from an AI event with a clear ask. Each Lace should:
- treat the leads it finds the way a good SDR does: cold at first, warm once
  they engage, hot when they're ready;
- never cold-email someone already in the founder's CRM;
- learn from the founder's real customers to find more like them;
- follow up when nobody answers.

## What a Lace already does

| Capability | Where |
|---|---|
| Finds accounts that match the ideal customer, each with a dated trigger, a fit score and a written reason | `agents/pipelines/accounts/`, `lace_accounts` (`score`, `fit_strength`, `fit`) |
| Finds contacts and checks their email (MX) | `agents/pipelines/accounts/contacts.py`, `lace_contacts` |
| Reads every reply and classifies it: interested, question, objection, meeting request, not now, unsubscribe, out of office, referral | `agents/pipelines/outreach/gtm_replies.py`, stored on `lace_outreach.intent` |
| Reads replies and bounces from Gmail and Outlook | `backend/app/services/inbox.py`, `scheduler.sync_inboxes` |
| Sums up the CRM pipeline, looks up a person or company, proposes adding a lead (founder approves) | `agents/lace/crm_tools.py`, `backend/app/services/crm.py`, `crm_actions.py` (Zoho CRM, HubSpot) |
| Never contacts someone marked do-not-contact | `lace_accounts.do_not_contact` |

## The gaps

1. **No temperature.** A lead that replied "interested" looks the same as one
   never contacted. The reply intent is stored, but nothing turns it into
   cold, warm or hot.
2. **No automatic CRM check.** A Lace can suggest, and draft to, a company
   that's already a customer or an open deal. The CRM is only checked when the
   model chooses to call `crm_lookup`.
3. **Customers don't shape the search.** Won deals are the best evidence of
   who buys, but the ideal customer is worked out from the website and what
   the founder says.
4. **No follow-ups.** After the first email, silence means nothing more
   happens.
5. **No "who to contact today".** Leads are ordered by fit only.

---

## Phase 0: GTM playbooks (the agent-skills pattern)

### What published GTM skills are
Open-source "agent skills" for GTM are now common. Each is a `SKILL.md`: a
name, a one-line description of when to use it, and a playbook the agent loads
only when the task calls for it. Examples, as of 2026-11-08:

| Collection | What it has |
|---|---|
| explorium-ai/gtm-skills | list-builder, enrich-contact, account-fit-rank, score-leads (Hot/Warm/Cold), personalize-email |
| LeadMagic/gtm-skills (leadmagic.io/gtm-skills) | A free directory: prospecting, ICP scoring, reply classification, cold email |
| gtmskills.com | Give-first cold email, list building, SDR follow-up messages by lead status |
| ColdIQ GTM skills | 137 sales triggers, 34 cold-email templates |
| zapier/gtm-cheat-codes | Daily Lead Steward: a daily view of the leads that need attention or follow-up |
| sales-skills/sales, gooseworks-ai/goose-skills | Large catalogues (100+ skills) across sales and marketing |

### Why we can't install them as they are
- **They're written for coding assistants** (Claude Code, Codex, Cursor), not
  for a Lace, which runs on Qwen inside our LangGraph loop.
- **Most call a vendor's data API** (Explorium, Apollo, Lemlist, Clay) that a
  Lace doesn't use. Lace's sources are Exa, BrightData and the founder's
  connected apps.
- **The good ones separate evidence from judgement.** Explorium's `score-leads`
  gathers evidence and states the rules, and says outright that it does not
  assign Hot/Warm/Cold: that's the caller's job. This matches Phase 1, where
  code sets the temperature from real signals.

### What we do instead
We take the **pattern**, and the **methods** in our own words, not the files:

1. **A playbook library** in `agents/prompts/playbooks/<name>.md`. Each has a
   name, a "use when" line and the method.
2. **Progressive disclosure, like SKILL.md.** The system prompt lists only each
   playbook's name and "use when" line, about one line each. A new
   `read_playbook(name)` tool loads the full text when the Lace starts that kind
   of task. Pipelines that always need one (drafting, replies, follow-ups) load
   it directly.
3. **The first playbooks:**
   - `cold-email`: give-first, founder-signed, one clear ask, short, a reason
     to write now from the account's trigger;
   - `follow-up`: what each follow-up adds (new value, not "just bumping
     this"), a shorter third touch, and stopping rules;
   - `reply-handling`: the next move for each reply intent (question, objection,
     not now, referral, meeting request);
   - `lead-temperature`: the rules from Phase 1, so the Lace explains a
     temperature the way the code set it;
   - `list-hygiene`: verify before sending, keep bounces under 2%, never
     re-contact an unsubscribe.
4. **Credit and licences.** We read a skill's licence before borrowing from it,
   and we write the playbook ourselves. Each playbook lists the sources it drew
   on.
5. **The founder can see them**, read-only in Settings, so they know how their
   Lace works. Their own standing instructions still override a playbook.

---

## Phase 1: lead temperature (cold, warm, hot, customer)

Each lead (account) gets a temperature. **Code sets it from signals, never
the model.** Each change records why, for example "Replied asking about
pricing, Nov 8".

| Temperature | When |
|---|---|
| **Cold** | Found, or contacted with no reply |
| **Warm** | Replied with a question, interest, an objection or a referral; engaged with the founder's posts or DMs (social listening); already in the founder's email history (Phase 2) |
| **Hot** | Asked for a meeting, agreed a time, or has a meeting on the founder's calendar |
| **Customer** | A won deal in the CRM, or the founder marks them as one |

- **Not now** keeps a lead warm, snoozed until a date. **Unsubscribe** sets
  `do_not_contact`.
- **Out of office** changes nothing.
- **Cooling:** warm with no activity for 30 days goes back to cold (a setting).
  Hot cools to warm after 30 days without a meeting.
- **Data:**
  - `lace_accounts` gains `temperature` (an enum, default `cold`),
    `temperature_reason` and `temperature_changed_at`, indexed for filtering;
  - a new `lace_account_signals` table records each signal: kind, when, source
    message or event, and the temperature before and after.
  - One migration. Existing accounts are backfilled from their outreach and
    reply intents, in a separate idempotent data migration.
- **UI:** a temperature badge and filter in People, a "Temperature" line on the
  account card with its reason, and Lace can answer "who's warm?".

## Phase 2: CRM awareness (when a CRM is connected)

- **A daily snapshot.** A bounded, read-only sync of the CRM's companies,
  contacts and deals (Zoho CRM, HubSpot) into `lace_crm_records`: domain,
  email, kind, stage, won or lost, and `synced_at`. It uses the existing
  `crm.py` readers and runs on the scheduler.
- **Leads already in the CRM aren't suggested as new.**
  - Account searches and contact searches check the snapshot by domain and by
    email.
  - A match isn't suggested as new. It's labelled "already in your CRM (stage:
    Negotiation)", and won deals become **customer**.
  - Drafting refuses to cold-email a CRM customer or open deal without the
    founder confirming.
- **The founder's email history.** Before a first email, check the founder's
  Gmail or Outlook for earlier mail with that domain. If there is any, the lead
  starts **warm**, and the draft reads as a follow-on, not a cold open.
- **Write-back, always on the founder's click.** When a lead turns warm or hot,
  Lace proposes adding it to the CRM, or moving its stage, through the existing
  approval cards.

## Phase 4: follow-ups (rounds of emailing)

- **Cadence (per-Lace settings):** no reply after **3 days** drafts follow-up 1,
  and no reply after another **7 days** drafts follow-up 2. Then the lead stays
  cold. At most **2** follow-ups.
- **Each follow-up is a draft in the same thread**, written with the
  `follow-up` playbook, and it waits for the founder's click like every send.
- **The sequence stops** on a reply, a bounce, an unsubscribe, a meeting, or
  the founder removing the lead.
- **Data:** outreach rows gain `sequence_step` and `follow_up_due_at`, and a
  scheduler sweep drafts the follow-ups that are due.

## Phase 3: learn from real customers (lookalikes)

- **Where customers come from:** the CRM's won deals (Phase 2), the "past
  customers" question in the welcome form, and accounts the founder marks as
  customers.
- **Characterise each customer:** read its site for industry, size, country,
  and the problem it had. They're saved as facts with sources.
- **Refine the ideal customer from them,** and say so: "Based on your 6
  customers, mostly clinic groups in Nairobi with 20–100 staff…".
- **Seed account searches** with customer examples: "find more like Aga Khan
  Clinics and Avenue Healthcare". Each lead names which customer it resembles
  and why.

## Phase 5: who to contact today

- **One ranking:** temperature first, then a fresh trigger, then fit, then
  time since the last touch. Hot first; then warm with a new signal; then
  follow-ups due; then new cold leads with a strong fit.
- **It feeds the daily brief** ("3 to reply to, 2 follow-ups ready, 4 new
  leads worth a first email") and a `who_to_contact_today` tool.

## Smaller improvements along the way

- **A bounce marks the contact's email invalid,** and the account is queued for
  another contact search.
- **Won and lost reasons:** when the founder marks a deal won or lost, the
  reason is saved as a fact, and later searches avoid the lost-deal patterns.

---

## Decisions (owner, 2026-11-08)

| Question | Decision |
|---|---|
| Temperature scale | Cold, warm, hot, plus customer |
| Order | Phase 0 playbooks, then 1 → 2 → 4 → 3 → 5 |
| Follow-up cadence | 3 days, then 7 days; at most 2 follow-ups |
| CRM write-back | Always on the founder's click |

## Rules that hold throughout

- **Nothing is sent or written to an app without the founder's click.**
- **Temperature, CRM matches and the ranking are computed in code** and
  explained in plain words. The model never guesses them.
- **Every list endpoint is paginated, and every sync and search is bounded**
  with a timeout.
- **One concern per PR, with its own migration and tests,** and a screenshot of
  any UI change.
