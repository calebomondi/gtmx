# Connected apps

The apps a founder can connect to Thalace, what a Lace does with each and why,
and what has to be set up first. The registry in code is
`backend/app/services/connections.APPS`; the app cards founders see are in
`frontend/src/features/connected-accounts/accounts-type.ts`.

## How connections work

- **Composio holds every connection.** It stores and refreshes the tokens; we
  never see a password. The Lace calls an app through Composio's tools
  (`connections.execute_tool`).
- **Shared accounts or a Lace's own.** An account a founder connects on the
  **Shared accounts** page is used by all their Laces. In a Lace's settings
  (Apps & accounts) they can connect an account just for that Lace instead,
  for a founder with several startups. A Lace uses its own account when it has
  one, else the shared one. If its own account needs reconnecting, it stops
  rather than falling back to the shared one, so one startup never sends as
  another.
- **A switch per Lace.** Each app can be switched on or off per Lace.
  Channels (email, socials) are on by default; work apps (CRM, sheets, docs,
  team, meetings) are on only where switched on, or when the founder has a
  single Lace.
- **Reading is free; writing needs a click.** The Lace reads freely. Anything
  that writes or sends in someone's name is a proposal (a card with Approve and
  Decline) or a draft the founder sends. The only standing writes are those the
  founder set up themselves (the brief to a Slack channel or Notion page).
- **Who can change it.** On a shared Lace, its admins and owner manage apps,
  accounts and settings; members see them read-only.
- **Managed vs own sign-in.** For most apps Composio provides the sign-in
  ("managed"). For TikTok and X it doesn't: we need our own developer app,
  registered with Composio as an auth config and listed in
  `COMPOSIO_AUTH_CONFIGS` (e.g. `{"tiktok": "ac_…", "twitter": "ac_…"}`).
  Until then, Connect for those apps is refused.

## Reading public profiles needs no connection

Public LinkedIn, X, Instagram, TikTok and Facebook profiles and posts (a
prospect's, a competitor's, the founder's own) are read through **Bright Data**
(`BRIGHTDATA_API_KEY`), with nothing connected. A profile read includes its
latest posts. Websites are read with **Firecrawl** (`FIRECRAWL_API_KEY`).

## The apps

### Channels: where a Lace reaches people

#### Gmail
- **Does:** sends the emails the founder approves (Send in Messaging), from
  their address. Replies and bounces are synced every few minutes and filed
  under the conversation they answer; the Lace reads them and drafts answers.
  The account's address labels the connection.
- **Why:** outreach that comes from the founder, not a no-reply tool, and
  replies the Lace can follow up.
- **Setup:** none (managed sign-in).
- **Limits:** at most 50 sends a day per founder across email and X
  (`MAX_OUTREACH_SENDS_PER_DAY`). Nothing is ever sent without a click.

#### Outlook
- **Does:** the same as Gmail for Microsoft 365 or Outlook.com: sends approved
  emails, answers inside the conversation, syncs replies. A Lace with both uses
  Gmail.
- **Why:** many B2B founders live in Outlook.
- **Setup:** none (managed).
- **Limits:** Outlook calendar slots aren't built yet. Not yet tried against a
  real Outlook account.

#### LinkedIn
- **Does:** shows who the founder is on drafts, and posts on LinkedIn when they
  approve a post the Lace proposed.
- **Why:** founder-led posting; LinkedIn is where many buyers are.
- **Setup:** none (managed).
- **Limits:** LinkedIn has no messaging API, so LinkedIn messages are drafted
  for the founder to paste and mark as sent. Reading other people's profiles
  uses Bright Data, not the connection.

#### X
- **Does, with nothing connected:** reads the founder's public posts and how
  they did (views, likes, replies, reposts), from the handle saved in the
  Lace's settings (Apps & accounts → X → Your public profile).
- **Does, once connected:** looks up profiles and posts through their account,
  sends DMs they approve, and posts, replies, likes and reposts on approval.
- **Why:** reach and engagement where tech buyers and investors are.
- **Setup:** our own X developer app, registered with Composio
  (`COMPOSIO_AUTH_CONFIGS` key `twitter`). Reading replies or searching needs
  a paid X API tier; check X's current pricing first.
- **Limits:** replies to the founder's posts can't be read without the X API;
  Bright Data gives only the reply count.

#### Instagram
- **Does:** reads the DMs sent to the founder's business account (linked to a
  Lace under Messaging → Inboxes) and drafts answers; sends answers on their
  click inside Meta's reply window; reads the comments on their recent posts
  to spot leads; replies to a comment on approval.
- **Why:** many consumer and SME startups sell through Instagram.
- **Setup:** none (managed); the account must be a professional (business or
  creator) account.
- **Limits:** Meta lets a business answer only people who wrote first, so a
  first message is sent by hand and marked sent; the Lace takes the
  conversation from there.

#### Facebook
- **Does:** the same for a Facebook Page: Page DMs, comments on Page posts,
  replies on approval, and Page posts on approval.
- **Setup:** none (managed). The Page must be one the founder manages.
- **Limits:** as Instagram.

#### TikTok
- **Does, with nothing connected:** reads the founder's public videos and how
  they did (views, likes, comments, shares), and the comments on their recent
  videos to find people worth reaching, from the handle saved in the Lace's
  settings. The comment read is slow, so it runs in the background and lands
  on the Feed.
- **Does, once connected:** nothing more yet.
- **Why:** many consumer startups grow on TikTok; comments are warm leads.
- **Setup:** none for the public reads. Connecting needs our own TikTok
  developer app (Login Kit, app review) registered with Composio (key
  `tiktok`).
- **Limits:** no API (official or not) posts a reply to a TikTok comment, so
  replies are drafted for the founder to paste. TikTok's official API doesn't
  give comments either; they come from public pages.

#### WhatsApp Business (Soon)
- **Planned:** start chats with the founder's approved templates and answer
  replies, like email.
- **Why it waits:** Composio can send WhatsApp messages but can't receive
  them. Replies need our own Meta app (business verification and app review)
  with a webhook on our backend. The plan is in the apps notes.

### CRM: the founder's pipeline

#### Zoho CRM and HubSpot
- **Does:** sums up the pipeline exactly, in code (deals and value by stage;
  open, won and lost; deals nobody touched for 30 days; deals closing within
  30 days); checks whether a person or company is already in the CRM before
  outreach; adds someone who showed interest as a lead, on approval.
- **Why:** the founder's numbers without opening the CRM, and no duplicate
  outreach to existing leads.
- **Setup:** none (managed). A Lace with both uses Zoho.
- **Limits:** Zoho's tool can't search, so a lookup reads up to 600 leads,
  contacts and accounts and matches them in code. Logging messages, and
  adding companies or deals, aren't built.

### Sheets & docs

#### Google Sheets
- **Does:** reads a sheet the founder links (a lead list, a pipeline), with
  each column's totals or counts worked out in code; imports a lead list as
  contacts once the founder says so; exports saved accounts or contacts to a
  new or existing sheet, on approval.
- **Setup:** none (managed).

#### Notion
- **Does:** searches the founder's pages and reads one (pricing, a playbook,
  customer notes); writes a page (a report, a plan) under a page they choose,
  on approval; and, if set under Brief in the Lace's settings, saves each brief
  as a page.
- **Setup:** none (managed). Notion only reaches the pages the founder shared
  with the connection when signing in.

### Team & tasks

#### Slack
- **Does:** searches the team's messages for context on a prospect or deal;
  posts a message to a channel on approval; and, if set under Brief, posts
  each brief to a channel.
- **Setup:** none (managed).

#### Asana
- **Does:** lists the founder's open tasks with overdue and due-this-week
  counts worked out in code; adds a follow-up task assigned to them, on
  approval.
- **Setup:** none (managed). Uses their first workspace.

### Meetings

#### Google Calendar
- **Does:** finds free slots in the next working days to offer in drafted
  replies.
- **Setup:** none (managed).

#### Calendly
- **Does (read only):** gives the founder's booking links for the Lace to put
  in drafts, and shows who booked meetings, marking people who are the Lace's
  contacts.
- **Setup:** none (managed).
- **Limits:** it uses the founder's existing booking links rather than making
  a link per prospect, which would be a write.

## Quick asks

A new chat shows one-tap questions for the apps a Lace can use ("Summarise my
pipeline", "What's overdue in Asana?"); see
`frontend/src/features/lace/quick-asks.ts`.

## Not yet tried for real

Outlook, Sheets, Notion, Slack, Asana, Zoho, HubSpot and Calendly were built
against Composio's documented tool shapes and tested with stubs; none has run
against a real account yet.
