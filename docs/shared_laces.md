# Shared Laces

A startup has one Lace, shared by its founding team. This is how several
people work with it at once: who may do what, how their messages take turns,
what each one's private chat is for, and how a private find reaches the team.

## People and roles

- **One Lace per startup.** A Lace is keyed by its website's domain
  (`laces.domain`). Someone who tries to make a second Lace for the same
  domain is told to ask to join it. Their request lands on the Lace's Feed
  for its people to let them in.
- **Roles.** The **owner** made it. **Admins** manage it with them: apps,
  settings, inviting and removing members. **Members** use it fully (chat,
  send drafts, approve app actions) but see its settings read-only. Only the
  owner archives or deletes it, makes admins, or removes an admin.
- **Invites** go to people who have already signed up, by email. Rows live in
  `lace_members` (status invited / requested / active / declined); access
  checks are `MemberLace`, `AdminLace` and `OwnerLace` in `api/deps.py`.

## The team chat

- **One conversation, signed.** Everyone talks to the Lace in the same chat.
  Each message carries its sender. On a Lace with a team, the model reads it
  as "[From Ama]", and the chat shows each sender's face.
- **One answer at a time.** The Lace answers one message at a time (the
  `uq_runs_one_active_per_lace` index). A message sent while it is busy
  waits its turn as a `queued` run and is answered when the turn before it
  ends, fails or is cancelled (`manager.start_next_queued`). Up to three can
  wait at once.
- **Who's talking.** While the Lace answers a cofounder, the chat says so
  ("Answering Ama", "Ama is talking to Shanga"), and the input stays open:
  what you send waits its turn.

## Team history on the Feed

Each Feed item names who did it or asked for it (`lace_activity.actor_id`),
on Laces with more than one person:

- **A search, its results and any failure** name the person who asked: by a
  button, or in chat (the job carries `params["actor_id"]`). The Lace's own
  work (scheduled checks, the brief, replies coming in) names nobody.
- **What people do is history too:** joining, sending a message (or marking
  one sent), saving a competitor, account or opportunity, approving an app
  action. These items arrive already read: nobody needs telling what they
  did themselves, and the Feed's seen state is shared.

## Private chats

On a Lace with a team, the chat has a **Team chat / Just you** switch. "Just
you" is a member's private chat with the same Lace:

- **Its own thread.** It is a separate LangGraph thread
  (`runs.lace.LaceThread`: `lace:{id}:member:{user}`). It runs beside the
  team's chat (`runs.owner_id`, `uq_runs_one_private_turn`). Only its member
  sees its messages, its runs, their progress and when it is busy.
- **Its finds are the member's.** The private Lace knows everything the
  team's Lace knows and uses the team's saved finds. What its searches find
  is filed under the member (`owner_id` on competitors, accounts and
  opportunities; jobs carry `params["private_to"]`). Those finds stay off the
  team's lists and Feed, and are reported back into the private chat
  (`lace_events.owner_id`).
- **It can't change the team's knowledge.** It cannot record or forget
  facts, rework the ideal customer profile, edit contacts or check the
  team's competitors (`graph.PRIVATE_WITHHELD`). If a member tells it
  something worth keeping, it suggests saying it in the team chat.
- **Drafts are shared.** Drafts it writes go to the team's Messaging, named as
  the member's, like any other.
- **A team-only feature.** A Lace with one person has no private chat: its
  team chat is already theirs.
- **Leaving.** A member who leaves or is removed takes their private chat
  and their unpushed finds with them. What they pushed stays for review.

## Push and review

- **Pushing.** In "Just you", the **Your finds** panel lists the private
  chat's finds. A member ticks what should go and pushes it to the team
  (`proposed_at`). The push lands on the Feed.
- **Before pushing,** a member can rename a find, reword what it is (a
  competitor's summary, an account's summary, an opportunity's why-it-fits),
  and leave the reviewer a note (`push_note`). They can also remove one: it
  is kept dismissed, so their chat doesn't suggest it again. While a find
  waits for review it is locked; it can change again once it is sent back.
  A later search that turns up the same company refreshes its name and
  description, overwriting a manual edit.
- **Reviewing.** The Feed's **To review** card lists teammates' pushes, each
  with what it is, its link and the member's note, and the "needs you" strip
  counts them. Any one other member decides: **Approve**
  or **Send back** with a note. Admins and the owner may also approve their
  own pushes.
- **Approving** makes the find the team's, saved (tracked / target / open). If
  the team already had the same company, the two are merged: the team's copy
  is saved and takes the private one's people and messages. The team's Lace
  hears of it, and who approved it, at its next turn.
- **Sending back** returns the find to the member, still private, with the
  note (`review_note`), shown in their Your finds panel.

The rules live in `backend/app/services/lace_finds.py`; the endpoints in
`backend/app/api/v1/endpoints/lace_finds.py`.

## Limits

- **One search per kind at a time.** A Lace runs one search of each kind at
  a time, whichever chat started it.
- **Shared seen state.** What has been seen on the Feed is shared by the
  team, not kept per person.
