# Sending email from our own domain

How to put `thalace.com` on Resend, so the waitlist and pilot emails reach
people, and how to send Supabase's sign-up emails from it too.

## What sends which email

| Email | Sent by | Turned on by |
|---|---|---|
| "You're on the Thalace waitlist" | Backend, through Resend (`backend/app/services/waitlist_emails.py`) | `RESEND_API_KEY` and `WAITLIST_FROM_EMAIL` |
| "You're in line for the Thalace pilot" (signup ticked the pilot box) | Backend, through Resend | Same |
| A Lace's daily brief by email | Backend, through Resend (`backend/app/services/lace_brief_email.py`) | Same |
| App sign-up confirmation, password reset | Supabase Auth | Custom SMTP in Supabase (step 5) |

`backend/app/services/email.py` sends nothing until both `RESEND_API_KEY` and
`WAITLIST_FROM_EMAIL` are set. Until then, signups are still saved and the
log says `Email not sent to …: Resend key or sender address not configured`.

## 1. Add the domain in Resend

1. Go to **resend.com → Domains → Add Domain** and enter `thalace.com`. Pick the
   region closest to your users.
2. Resend lists the DNS records to add. Copy each value from that page exactly:

   | Type | Name | Value |
   |---|---|---|
   | MX | `send` | Resend's feedback host, priority 10 (handles bounces) |
   | TXT | `send` | SPF: `v=spf1 include:amazonses.com ~all` |
   | TXT | `resend._domainkey` | The DKIM public key |

3. Add them at your DNS provider:
   - **Cloudflare:** set each record to **DNS only** (grey cloud).
   - **Names:** if the provider appends the domain itself, enter `send`, not
     `send.thalace.com`.
4. Add a DMARC record, which Gmail and Yahoo expect from bulk senders:

   | Type | Name | Value |
   |---|---|---|
   | TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:hello@thalace.com` |

5. In Resend, click **Verify**. It usually passes within minutes, though DNS can
   take up to a few hours.

These records are on the `send.` subdomain, so they don't clash with any
mailbox MX on the root domain.

## 2. Make sure replies reach someone

Both waitlist emails say "Reply to this email…" (reply "pilot", or reply to be
removed). Resend only sends, so the From address must also be a real inbox.
Make `hello@thalace.com` one you read, through any of:
- Google Workspace
- Zoho Mail
- Cloudflare Email Routing, forwarding to an existing inbox

## 3. Set the sender

**Production (Render):** on the `api` service, open **Environment** and add:

```
WAITLIST_FROM_EMAIL=Thalace <hello@thalace.com>
```

`RESEND_API_KEY` is already declared in `render.yaml`. Make sure it holds a key
from the Resend account that verified the domain. Then redeploy.

**Locally:** put the same two variables in `.env`.

## 4. Test it

1. On thalace.com, sign up with your own email and tick the pilot box. Two
   emails should arrive:
   - "You're on the Thalace waitlist"
   - "You're in line for the Thalace pilot"
2. If nothing arrives, search the API logs for `Resend refused the email to`.
   That line includes Resend's status and reason, usually that the domain isn't
   verified.
3. Resend's **Emails** page shows whether each one was delivered, bounced or
   marked as spam.

## 5. Supabase's sign-up emails

When a pilot user signs up in the app, Supabase sends their confirmation and
password-reset emails, not our code. Supabase's built-in sender:
- allows only a few emails an hour;
- sends from a Supabase address.

To send them through Resend from our domain, go to **Supabase → Project
Settings → Authentication → SMTP Settings → Enable custom SMTP**:

| Field | Value |
|---|---|
| Host | `smtp.resend.com` |
| Port | `465` |
| Username | `resend` |
| Password | A Resend API key (a separate one named `supabase` makes it easy to revoke alone) |
| Sender email | `hello@thalace.com` |
| Sender name | `Thalace` |

Then:
- raise the email limit under **Authentication → Rate Limits**;
- optionally, edit the wording under **Authentication → Email Templates**.
