# What a Lace can read and write in each app

A live check on the owner's account, on 2026-11-05, covered both Laces, Thalesis
and Shanga. Each check ran through the same code the Lace uses.

- **Tested live:** the read or write ran against the real account.
- **Writes:** each test write was undone straight away: a draft deleted, an event
  cancelled, a page archived, or a row added to the "Thalace check" test sheet.
- **Not tested live:** anything that would reach a real person or post publicly. These
  are covered by the automated tests instead.

## App by app

| App | Reads | Writes (each only on the founder's approval or click) | Notes |
|---|---|---|---|
| **Gmail** | Search the inbox; open whole threads. Tested live. | Send email; reply in a thread. A draft was created and deleted live, which proves write access. A real send wasn't tested, because it would email someone. | The owner's personal Gmail is read only in chats the owner starts. |
| **Outlook** | List messages. Tested live. | Send and reply. New email can go from Outlook (the "New email goes from" choice). A real send wasn't tested; the automated tests cover it. | Each conversation's answer goes out from the mailbox it's in. |
| **Google Calendar** | Events with attendees, times and links; free slots. Tested live. | Create, move and cancel meetings. Tested live: the test event was created, moved and cancelled. | |
| **Google Sheets** | Find a sheet by name and read it. Tested live on Thalesis. | Add or update rows. Tested live on Thalesis (a row added to the test sheet). | **Shanga is refused:** it uses the founder's shared Sheets account, which was connected without every permission. Reconnect it and tick every access box. |
| **Notion** | Search and read pages. Tested live. | Create a page. Tested live: the test page was archived. | |
| **Calendly** | Scheduling links and meetings. Tested live. | None. It shares the scheduling link instead of booking. | |
| **Instagram** | Comments on the founder's posts; DMs. Tested live. | Reply to a comment. Not tested live, because it would be public. | |
| **Facebook** | The linked Page's posts and comments, and the Pages the founder manages. | Post to the Page; reply to a comment. Not tested live, because it would be public. | Every comment read used to be refused. Fixed in #418: the linked Page now reads cleanly, and its posts have no comments yet. Each Lace needs a Page linked; Thalesis has one, Shanga doesn't yet. |
| **Telegram** | The bot's profile, and people who write to the bot. Tested live. | Send a message. Not tested live, because it would message a real person. | Each Lace needs its bot linked. |
| **X** (by the founder's handle) | The founder's own posts with their numbers (5 posts), and mentions. Tested live on Thalesis. | Post, reply, like and repost. Not tested live. | Shanga has no handle saved. |
| **TikTok** (by the founder's handle) | The founder's own videos (0) and comments. Tested live on Thalesis. | None. | Shanga has no handle saved. |
| **LinkedIn** | None: LinkedIn doesn't let apps read posts or comments. | Publish a post. The Lace drafts notes to people, and the founder sends them. | Sending LinkedIn messages through the app isn't possible. |
| **Slack** | Search messages. | Post a message, including the daily brief to a chosen channel. | Not connected, so not tested live; the automated tests cover it. |
| **HubSpot / Zoho CRM** | Deals; find a lead. | Add a lead. | Not connected, so not tested live; the automated tests cover it. |
| **Asana** | Tasks. | Create a task. | Not connected, so not tested live; the automated tests cover it. |

## What a Lace never does

- **Nothing without the founder.** It never writes, sends or posts on its own. It drafts or proposes, and the action runs only when the founder approves or clicks Send.
- **No first message on social media.** First contact is always email, or a LinkedIn note the founder sends by hand.
- **No account it isn't allowed to use:**
  - an app switched off for that Lace;
  - the owner's personal Gmail or Calendar in a cofounder's chat;
  - a mailbox other than the one the founder picked for new email.
- **No swapping accounts.** If the chosen mailbox is gone, sending stops and says so.

## Which account a Lace uses

- **Shared by default.** Every connected app is on in every Lace (since #417). A Lace uses its own account where it has one, else the founder's shared one. The founder can switch an app off in one Lace.
- **Pages and bots.** Facebook, Instagram and Telegram also need a Page, business account or bot linked to the Lace. The Social tab and Settings → Apps show a "pick one" card until it's done.

## To fix on the owner's account

1. Reconnect the **shared Google Sheets** account under Shared accounts, and tick every access box. Shanga uses it.
2. On **Shanga**, link a Facebook Page and save the X and TikTok handles.
3. Delete the **"Thalace check"** test sheet.
