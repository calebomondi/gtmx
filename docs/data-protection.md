# Data protection: Thalace's roles, the laws that apply, and what to do

**Not legal advice.** This is a map to take to a Kenyan data-protection lawyer.
The law's structure below is reliable. Thresholds, fees and the list of sectors
that must register are marked *to confirm*: check them with the Office of the
Data Protection Commissioner (ODPC) before acting on them.

_Written 2026-11-06, after a founder in the community asked whether Thalace is a
"data handler" when their connected apps hold business and sensitive data._

---

## 1. Is Thalace a data handler?

Yes, in two roles. Kenya's Data Protection Act, 2019 defines:
- a **data controller**, who decides why and how personal data is used;
- a **data processor**, who handles it on a controller's behalf.

| Situation | Thalace's role | The founder's role |
|---|---|---|
| Founders' own accounts: sign-up email, usage, waitlist answers | **Controller** | Data subject |
| A founder connects Gmail, Outlook, Calendar, Sheets, Notion, Slack, a CRM or social accounts, and Lace reads them on the founder's request | **Processor**, acting on their instruction | **Controller** of their customers' and contacts' data |
| Lace **finds people** (prospects at target companies) from the web, LinkedIn and social profiles | Likely **controller, or joint controller with the founder**, because Thalace's own system decides how those people are found | Joint controller |

**The third row carries the most risk.** Lace collects personal data about
people who never signed up to Thalace.

### Business data isn't personal data
Revenue figures, pricing, strategy and other business information aren't
covered by the Data Protection Act. They're protected by Thalace's terms of
service and confidentiality obligations instead. The Act covers information
about **identifiable people**: names, emails, phone numbers, and the contents of
emails or documents about them.

---

## 2. The laws that apply

### Kenya

**Data Protection Act, 2019.** The core law. The parts that matter most for
Thalace:

| Section | What it requires |
|---|---|
| s.25 | The principles: lawful, fair, transparent; collected for a stated purpose; minimal; accurate; kept no longer than needed; secure |
| s.26 | Data subjects' rights: to be informed, to access, to object, to correct, to delete |
| s.29 | Telling people when their data is collected, including when it comes from somewhere other than them |
| s.30 | A lawful basis for processing: consent, a contract, a legal duty, or legitimate interests, among others |
| s.31 | A **data protection impact assessment** before processing likely to be high risk, such as profiling |
| s.37 | Using personal data for **commercial purposes** only with consent or another legal basis. This matters for outreach. |
| s.43 | Notifying the ODPC of a **breach within 72 hours**, and the people affected where there's a real risk to them |
| ss.48–50 | Sending personal data **out of Kenya** only with proof of appropriate safeguards |

**Data Protection (General) Regulations, 2021.** The details, including:
- the rules for **direct marketing**: an opt-out in every marketing message;
- how to handle data subject requests.

**Data Protection (Registration of Data Controllers and Data Processors)
Regulations, 2021:**
- You must **register with the ODPC** above a size threshold. *To confirm:* I
  believe it's an annual turnover over KES 5 million, or more than 10 staff.
- Some sectors must register whatever their size. *To confirm:* I believe the
  list includes **direct marketing**, which is close to what Lace does.
- The fee scales with company size. *To confirm:* from about KES 4,000 for a
  small company.
- The certificate must be renewed.

**Computer Misuse and Cybercrimes Act, 2018.** Unauthorised access and data
security.

**Consumer Protection Act, 2012.** Fair terms with customers.

### Outside Kenya

- **GDPR (EU) and UK GDPR.** The waitlist is worldwide. Users, or prospects
  Lace finds, in the EU or UK bring these in. They have a very similar
  structure to Kenya's Act.
- **Google API Services User Data Policy.** Reading Gmail through an app
  requires Google's app verification and a security assessment for restricted
  scopes. Check whether Composio's verified Google app covers Thalace, or
  whether Thalace needs its own verified OAuth client.
- **Platform terms** for X, Meta (Facebook, Instagram), LinkedIn, TikTok and
  Telegram, on what may be read, stored and sent.

---

## 3. Where the data goes: sub-processors

Every service that receives personal data on Thalace's behalf is a
sub-processor. This list comes from `config.py` and `render.yaml` as of
2026-11-06. Confirm each provider's data region and terms.

| Service | What it does for Thalace | Personal data it can receive |
|---|---|---|
| **Render** (Frankfurt, EU) | Hosts the API and the background agents | Everything the app processes |
| **Supabase** | Sign-in, and the production Postgres database | Account emails; everything stored |
| **Alibaba Cloud DashScope** (Qwen) | Main AI model | Prompts: facts about the startup, conversation, email and document contents the Lace reads |
| **OpenRouter** | Backup AI model, and the models it routes to | The same as DashScope, when it's used |
| **Exa**, **Firecrawl** | Web search and reading pages | Search queries, sometimes including people's or companies' names |
| **BrightData** | LinkedIn, X, Instagram and TikTok profiles | Profile URLs; public profile data it returns |
| **Composio** | Connections to the founder's apps (Gmail, Outlook, Calendar, Sheets, Notion, Slack, CRMs, social accounts) | OAuth tokens; whatever is read from or sent through those apps |
| **Resend** | Thalace's own emails: waitlist, pilot, daily brief | Recipient emails; the brief's contents |
| **Sentry** (if `SENTRY_DSN` is set) | Error reports | Error context, which can include user identifiers |
| **LangSmith** (if `LANGSMITH_API_KEY` is set) | Agent traces | **Full prompts and scraped pages.** Leave it off in production, or treat it as a full sub-processor. |

**For the cross-border rules (ss.48–50), Thalace needs:**
- this list, published;
- each provider's data processing agreement or equivalent safeguards on file;
- confirmation that the **AI model providers' terms don't allow them to train on
  or keep** users' data.

---

## 4. Gaps today, and what to do

In order of urgency:

1. **There's no privacy policy or terms of service.**
   - On the app's sign-up form, "Terms of Service" and "Privacy Policy" link to
     `#` (`frontend/src/components/signup-form.tsx`), so people are agreeing to
     documents that don't exist.
   - Write both, publish them on thalace.com, and link them from the app's
     sign-up, the waitlist form and every email footer.
2. **ODPC registration.** Check the threshold and the sector list (section 2).
   If either applies, register and keep the certificate current.
3. **Cross-border transfers.** Publish the sub-processor list (section 3), file
   each provider's data processing agreement, and confirm no AI provider trains
   on users' data.
4. **A data processing agreement for customers.** The terms should say that
   Thalace processes connected-app data only on the founder's instructions, for
   the founder's purposes, and lists its sub-processors.
5. **Prospect data** (people Lace finds):
   - choose a lawful basis (usually legitimate interests) and write down the
     legitimate-interests assessment;
   - tell people where their data came from when they're first contacted (s.29);
   - give anyone an easy way to be removed and never found again. Lace's
     "removed, not suggested again" lists already help with the last part.
6. **A data protection impact assessment** for finding people and profiling
   accounts (s.31). It's likely required, and it's good practice anyway.
7. **Outreach.**
   - The founder sends, and is the controller for their outreach.
   - Drafts should support an opt-out line, as the direct-marketing rules
     require.
8. **Security, breaches and retention.**
   - Write a 72-hour breach plan: who decides, who notifies the ODPC, and the
     message to users.
   - Decide how long data is kept, including what's kept from an app after it's
     disconnected and after an account is deleted.
   - Keep OAuth tokens with Composio rather than in Thalace's database, and keep
     access to production data limited.
9. **Data subject requests.** A simple process for access and deletion requests
   (for example privacy@thalace.com), answered within the Act's time limits.
   Admins can already take people off the pilot; full deletion should exist
   for every kind of data, not just the waitlist.

---

## 5. A reply for the community

> Great question. When you connect your apps, Thalace processes that data only to do what you ask, so you stay in control of your customers' data, and we act as your processor under Kenya's Data Protection Act 2019. Your business data stays yours: we don't sell it or use it to train AI models, and nothing is sent without your click. We're finalising our privacy policy and data processing terms before launch and will share them here. If you have specific requirements, tell us. It helps us get it right.

Only say "we don't … use it to train AI models" once each AI provider's terms
confirm it (section 3).

---

## 6. Next steps

- [ ] Book a Kenyan data-protection lawyer; bring this document.
- [ ] Confirm ODPC registration requirements and register if they apply.
- [ ] Draft the privacy policy, terms of service and customer data processing
      terms from what the code actually does, for the lawyer to review.
- [ ] Collect each sub-processor's data processing agreement and AI-training
      terms.
- [ ] Write the legitimate-interests assessment and the impact assessment for
      finding prospects.
- [ ] Write the breach plan and the retention rules.
- [ ] Replace the `#` links on the sign-up form once the documents exist.
