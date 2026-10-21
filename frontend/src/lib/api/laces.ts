import { apiFetch } from "./http"

export type LaceStatus = "onboarding" | "active" | "archived"

export type FactTopic =
  | "company"
  | "offer"
  | "pricing"
  | "customers"
  | "market"
  | "competition"
  | "icp"
  | "positioning"

export interface LaceDto {
  id: string
  name: string
  website: string
  startup_name: string | null
  status: LaceStatus
  /** Shown first in the sidebar. */
  pinned: boolean
  created_at: string
}

/** What is actually going on with a Lace: working now, or waiting on the founder. */
export type LaceMood = "thinking" | "alert"

export interface LaceListItemDto extends LaceDto {
  mood: LaceMood | null
  last_active_at: string
}

export interface FactDto {
  id: string
  topic: FactTopic
  claim: string
  source_url: string | null
  confidence: "high" | "medium" | "low"
  origin: "crawl" | "research" | "user" | "monitor"
  recorded_at: string
  /** When the founder confirmed it; null until then. */
  confirmed_at: string | null
}

/** The founder's verdict on a fact: right, or wrong (it leaves what the Lace knows). */
export type FactVerdict = "confirmed" | "retracted"

export type CardKind = "competitor" | "account" | "opportunity" | "draft"

/** Answers the founder can click instead of typing. */
export interface ChoicesBlockDto {
  type: "choices"
  /** Null on choices from before answers were kept; those can't be answered. */
  id?: string | null
  question: string
  options: string[]
}

export interface ChecklistItemDto {
  id: string
  label: string
  detail: string | null
  checked: boolean
}

/** Items the founder ticks, then submits. Mirrors ChecklistBlock. */
export interface ChecklistBlockDto {
  type: "checklist"
  id: string
  question: string
  items: ChecklistItemDto[]
  submit: string
}

export type FormFieldKind = "text" | "long_text" | "email" | "url" | "number"

export interface FormFieldDto {
  name: string
  label: string
  kind: FormFieldKind
  required: boolean
  value: string | null
}

/** A few short fields the founder fills in. Mirrors FormBlock. */
export interface FormBlockDto {
  type: "form"
  id: string
  question: string
  fields: FormFieldDto[]
  submit: string
}

export type QuestionBlockDto = ChoicesBlockDto | ChecklistBlockDto | FormBlockDto

/** The founder's answer to a question. Mirrors BlockAnswer. */
export interface BlockAnswerDto {
  block_id: string
  /** The option picked (a choice) or the item ids ticked (a checklist). */
  chosen: string[]
  /** A form's answers, by field name. */
  values: Record<string, string>
}

/** A snapshot of one saved item, as it was when the Lace showed it. */
export interface CardBlockDto {
  type: "card"
  kind: CardKind
  id: string
  title: string
  subtitle: string | null
  body: string | null
  url: string | null
  /** Where the item stands now (e.g. open, dismissed); "gone" once it no longer exists. */
  status?: string | null
}

export type UiBlockDto = QuestionBlockDto | CardBlockDto

export interface AttachmentDto {
  id: string
  filename: string
}

export interface LaceMessageDto {
  role: "founder" | "lace"
  content: string
  /** Cards and choices under a Lace reply. */
  ui?: UiBlockDto[]
  /** What the founder attached to their message. */
  documents?: AttachmentDto[]
  /** The question this founder message answered. */
  answer?: BlockAnswerDto
}

/** A document shared with a Lace, kept as its text. Mirrors DocumentResponse. */
export interface LaceDocumentDto {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  /** Only the start of a very long document was kept. */
  truncated: boolean
  created_at: string
}

/** File kinds a Lace can read, for the file picker. */
export const DOCUMENT_ACCEPT = ".pdf,.docx,.pptx,.txt,.md,.markdown,.csv,.tsv,.json"

export function uploadLaceDocument(laceId: string, file: File): Promise<LaceDocumentDto> {
  const body = new FormData()
  body.append("file", file)
  return apiFetch(`/api/v1/laces/${laceId}/documents`, { method: "POST", body })
}

export function listLaceDocuments(laceId: string): Promise<LaceDocumentDto[]> {
  return apiFetch<LaceDocumentDto[]>(`/api/v1/laces/${laceId}/documents`)
}

export function deleteLaceDocument(laceId: string, documentId: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/documents/${documentId}`, { method: "DELETE" })
}

/** The browser's IANA timezone, e.g. "Africa/Nairobi": when the founder's day starts. */
export function localTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone
}

export function createLace(name: string, website: string): Promise<{ lace: LaceDto; run_id: string }> {
  return apiFetch("/api/v1/laces", { method: "POST", body: JSON.stringify({ name, website, timezone: localTimeZone() }) })
}

/** The founder's Laces, most recently active first. */
export function listLaces(): Promise<LaceListItemDto[]> {
  return apiFetch<LaceListItemDto[]>("/api/v1/laces")
}

export function updateLace(laceId: string, changes: { pinned?: boolean }): Promise<LaceDto> {
  return apiFetch(`/api/v1/laces/${laceId}`, { method: "PATCH", body: JSON.stringify(changes) })
}

/** Archived Laces: out of the sidebar's crew and doing no work until restored. */
export function listArchivedLaces(): Promise<LaceDto[]> {
  return apiFetch<LaceDto[]>("/api/v1/laces/archived")
}

/** 409 while the Lace is working. */
export function archiveLace(laceId: string): Promise<LaceDto> {
  return apiFetch(`/api/v1/laces/${laceId}/archive`, { method: "POST" })
}

export function restoreLace(laceId: string): Promise<LaceDto> {
  return apiFetch(`/api/v1/laces/${laceId}/restore`, { method: "POST" })
}

/** For good, with everything it found and wrote. 409 while the Lace is working. */
export function deleteLace(laceId: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}`, { method: "DELETE" })
}

/** Read the site again after an onboarding that failed. */
export function retryLaceOnboarding(laceId: string): Promise<{ run_id: string }> {
  return apiFetch(`/api/v1/laces/${laceId}/onboarding`, { method: "POST" })
}

export function getLace(laceId: string): Promise<LaceDto> {
  return apiFetch<LaceDto>(`/api/v1/laces/${laceId}`)
}

export function listLaceFacts(laceId: string): Promise<FactDto[]> {
  return apiFetch<FactDto[]>(`/api/v1/laces/${laceId}/facts`)
}

export function reviewLaceFact(laceId: string, factId: string, verdict: FactVerdict): Promise<FactDto> {
  return apiFetch(`/api/v1/laces/${laceId}/facts/${factId}`, { method: "PATCH", body: JSON.stringify({ verdict }) })
}

/** The founder's own wording replaces the fact; returns the new fact. */
export function correctLaceFact(laceId: string, factId: string, claim: string): Promise<FactDto> {
  return apiFetch(`/api/v1/laces/${laceId}/facts/${factId}/correction`, { method: "POST", body: JSON.stringify({ claim }) })
}

export function listLaceMessages(laceId: string): Promise<LaceMessageDto[]> {
  return apiFetch<LaceMessageDto[]>(`/api/v1/laces/${laceId}/messages`)
}

/** Starts a turn; follow its run for the reply. */
/** A message to the Lace; `documentIds` are documents uploaded to it first. */
/** Answer a question under the Lace's latest reply; 409 once it was answered. */
export function answerLaceQuestion(laceId: string, answer: BlockAnswerDto): Promise<{ run_id: string }> {
  return apiFetch(`/api/v1/laces/${laceId}/messages`, { method: "POST", body: JSON.stringify({ answer }) })
}

export function sendLaceMessage(laceId: string, text: string, documentIds: string[] = []): Promise<{ run_id: string }> {
  return apiFetch(`/api/v1/laces/${laceId}/messages`, {
    method: "POST", body: JSON.stringify({ text, document_ids: documentIds }),
  })
}

/** suggested: a search found it and it waits for the founder to save (tracked) or dismiss. */
export type CompetitorStatus = "suggested" | "tracked" | "dismissed"

export interface LaceCompetitorDto {
  id: string
  name: string
  website: string
  summary: string | null
  origin: "found" | "founder"
  status: CompetitorStatus
  first_seen_at: string
  last_seen_at: string
}

export function listLaceCompetitors(laceId: string, status: CompetitorStatus = "tracked"): Promise<LaceCompetitorDto[]> {
  return apiFetch<LaceCompetitorDto[]>(`/api/v1/laces/${laceId}/competitors?status=${status}`)
}

export type MoveKind =
  | "pricing" | "product" | "positioning" | "funding" | "leadership" | "partnership" | "event" | "social" | "news"
  | "client"

/** A material move a tracked competitor made. Mirrors MoveResponse. */
export interface LaceMoveDto {
  id: string
  competitor_id: string
  competitor_name: string
  kind: MoveKind
  importance: "high" | "medium" | "low"
  title: string
  summary: string
  /** What it means for the startup. */
  implication: string | null
  /** The move to make in response. */
  counter_move: string | null
  sources: string[]
  detected_at: string
}

/** What the tracked competitors did, newest first. */
export function listLaceMoves(laceId: string): Promise<LaceMoveDto[]> {
  return apiFetch<LaceMoveDto[]>(`/api/v1/laces/${laceId}/moves`)
}

export function setLaceCompetitorStatus(laceId: string, competitorId: string, status: Exclude<CompetitorStatus, "suggested">): Promise<LaceCompetitorDto> {
  return apiFetch(`/api/v1/laces/${laceId}/competitors/${competitorId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  })
}

/** suggested: a search found it and it waits for the founder to save (target) or dismiss. */
export type AccountStatus = "suggested" | "target" | "dismissed"

export interface LaceAccountDto {
  id: string
  name: string
  account_type: string
  website: string | null
  geo: string | null
  summary: string | null
  trigger: { event: string; source: string | null } | null
  /** Why the startup suits this account now; null if it could not be made. */
  case: { need: string; capability: string; payoff: string; angle: string | null; strength: "strong" | "moderate" | "weak" } | null
  status: AccountStatus
  /** person: someone named is reachable; organisation: only its own channels; none: nothing found. */
  contact_status: "person" | "organisation" | "none" | null
  contacts: { name: string | null; title: string | null; email: string | null; linkedin: string | null }[]
  /** The organisation's own pages, by platform. */
  channels: Record<string, string>
  contacts_checked_at: string | null
  first_seen_at: string
  last_seen_at: string
}

export function listLaceAccounts(laceId: string, status: AccountStatus = "target"): Promise<LaceAccountDto[]> {
  return apiFetch<LaceAccountDto[]>(`/api/v1/laces/${laceId}/accounts?status=${status}`)
}

export function setLaceAccountStatus(laceId: string, accountId: string, status: Exclude<AccountStatus, "suggested">): Promise<LaceAccountDto> {
  return apiFetch(`/api/v1/laces/${laceId}/accounts/${accountId}`, { method: "PATCH", body: JSON.stringify({ status }) })
}

export type OutreachChannel = "email" | "linkedin" | "x" | "instagram" | "facebook" | "tiktok"

export interface LaceOutreachDto {
  id: string
  account_id: string | null
  channel: OutreachChannel
  direction: "outbound" | "inbound"
  status: "draft" | "sending" | "sent" | "failed" | "bounced" | "received"
  recipient_name: string | null
  recipient_company: string
  /** An email address, or the profile or page URL on any other channel. */
  recipient_address: string | null
  subject: string | null
  body: string
  /** Set on sent emails, replies, and answers drafted in their thread. */
  thread_id: string | null
  /** Inbound only: how the reply was read, e.g. "interested", "question". */
  intent: string | null
  error: string | null
  sent_at: string | null
  created_at: string
}

export type LaceOutreachChanges = Partial<Pick<LaceOutreachDto, "subject" | "body" | "recipient_address" | "recipient_name">>

export function listLaceOutreach(laceId: string): Promise<LaceOutreachDto[]> {
  return apiFetch<LaceOutreachDto[]>(`/api/v1/laces/${laceId}/outreach`)
}

export function updateLaceOutreach(laceId: string, messageId: string, changes: LaceOutreachChanges): Promise<LaceOutreachDto> {
  return apiFetch(`/api/v1/laces/${laceId}/outreach/${messageId}`, { method: "PATCH", body: JSON.stringify(changes) })
}

export function deleteLaceOutreach(laceId: string, messageId: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/outreach/${messageId}`, { method: "DELETE" })
}

/** Send an email draft through the founder's Gmail: the founder's own action. */
export function sendLaceOutreach(laceId: string, messageId: string): Promise<LaceOutreachDto> {
  return apiFetch(`/api/v1/laces/${laceId}/outreach/${messageId}/send`, { method: "POST" })
}

/** Record a LinkedIn message the founder sent by hand. */
export function markLaceOutreachSent(laceId: string, messageId: string): Promise<LaceOutreachDto> {
  return apiFetch(`/api/v1/laces/${laceId}/outreach/${messageId}/mark-sent`, { method: "POST" })
}

export type InboxPlatform = "instagram" | "facebook"

export interface LaceChannelDto {
  id: string
  platform: InboxPlatform
  account_id: string
  account_name: string
  synced_until: string | null
  created_at: string
}

export interface ChannelAccountDto {
  id: string
  name: string
}

/** The Instagram and Facebook accounts whose DMs this Lace reads. */
export function listLaceChannels(laceId: string): Promise<LaceChannelDto[]> {
  return apiFetch<LaceChannelDto[]>(`/api/v1/laces/${laceId}/channels`)
}

/** Accounts the founder's connected Instagram or Facebook manages. */
export function listAvailableChannels(laceId: string, platform: InboxPlatform): Promise<ChannelAccountDto[]> {
  return apiFetch<ChannelAccountDto[]>(`/api/v1/laces/${laceId}/channels/available?platform=${platform}`)
}

export function linkLaceChannel(laceId: string, platform: InboxPlatform, accountId: string): Promise<LaceChannelDto> {
  return apiFetch(`/api/v1/laces/${laceId}/channels`, {
    method: "POST", body: JSON.stringify({ platform, account_id: accountId }),
  })
}

export function unlinkLaceChannel(laceId: string, channelId: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/channels/${channelId}`, { method: "DELETE" })
}

export type OpportunityKind = "showcase" | "sell" | "partner"
/** suggested: a search found it and it waits for the founder to save (open) or dismiss. */
export type OpportunityStatus = "suggested" | "open" | "dismissed"

export interface LaceOpportunityDto {
  id: string
  kind: OpportunityKind
  title: string
  organiser: string | null
  url: string
  deadline: string | null
  event_date: string | null
  location: string | null
  why_it_fits: string
  how_to_act: string
  status: OpportunityStatus
  first_seen_at: string
}

/** Open opportunities (none past their deadline or date), soonest first. */
export function listLaceOpportunities(laceId: string, status: OpportunityStatus = "open"): Promise<LaceOpportunityDto[]> {
  return apiFetch<LaceOpportunityDto[]>(`/api/v1/laces/${laceId}/opportunities?status=${status}`)
}

/** Save an opportunity (open) or drop it (dismissed: not for us). */
export function setLaceOpportunityStatus(laceId: string, opportunityId: string,
                                         status: Exclude<OpportunityStatus, "suggested">): Promise<LaceOpportunityDto> {
  return apiFetch(`/api/v1/laces/${laceId}/opportunities/${opportunityId}`, {
    method: "PATCH", body: JSON.stringify({ status }),
  })
}

export type BriefFrequency = "off" | "daily" | "weekly"

/** Local hours [start, end) in which nothing is emailed; end may be before start (overnight). */
export interface QuietHoursDto {
  start: number
  end: number
}

export interface BriefSettingsDto {
  brief_frequency: BriefFrequency
  /** Local hour, 0–23, in `timezone`. */
  brief_hour: number
  timezone: string
  /** Also email each brief to the founder. */
  brief_email: boolean
  quiet_hours: QuietHoursDto | null
  /** Whether this server can send email at all. */
  email_available: boolean
  last_brief_at: string | null
}

export type BriefSettingsChanges = Partial<Pick<BriefSettingsDto,
  "brief_frequency" | "brief_hour" | "timezone" | "brief_email" | "quiet_hours">>

export function getLaceBrief(laceId: string): Promise<BriefSettingsDto> {
  return apiFetch<BriefSettingsDto>(`/api/v1/laces/${laceId}/brief`)
}

export function updateLaceBrief(laceId: string, changes: BriefSettingsChanges): Promise<BriefSettingsDto> {
  return apiFetch(`/api/v1/laces/${laceId}/brief`, { method: "PATCH", body: JSON.stringify(changes) })
}

export type ActivityKind =
  | "brief"
  | "competitors_found"
  | "competitor_moves"
  | "accounts_found"
  | "contacts_found"
  | "drafts_ready"
  | "reply_received"
  | "opportunities_found"
  | "job_failed"

/** Something the Lace did or found, for its Feed. */
export interface ActivityDto {
  id: string
  kind: ActivityKind
  title: string
  summary: string | null
  ref_type: "brief" | "outreach" | null
  ref_id: string | null
  created_at: string
  /** When the founder saw it in the Feed; null while unseen. */
  read_at: string | null
}

/** Newest first; `before` (an item's created_at) pages back. */
export function listLaceActivity(laceId: string, before?: string): Promise<ActivityDto[]> {
  const query = before ? `?before=${encodeURIComponent(before)}` : ""
  return apiFetch<ActivityDto[]>(`/api/v1/laces/${laceId}/activity${query}`)
}

export function markLaceActivityRead(laceId: string): Promise<{ marked: number }> {
  return apiFetch(`/api/v1/laces/${laceId}/activity/read`, { method: "POST" })
}

/** An activity in the feed across all the founder's Laces. */
export interface LaceActivityItemDto extends ActivityDto {
  lace_id: string
  lace_name: string
}

/** Newest first across every Lace; `before` (an item's created_at) pages back. */
export function listAllLaceActivity(before?: string): Promise<LaceActivityItemDto[]> {
  const query = before ? `?before=${encodeURIComponent(before)}` : ""
  return apiFetch<LaceActivityItemDto[]>(`/api/v1/laces/activity${query}`)
}

/** How far a Lace's target accounts have come. Counts of distinct accounts. */
export interface FunnelDto {
  accounts: number
  contacted: number
  replied: number
  interested: number
}

export function getLaceFunnel(laceId: string): Promise<FunnelDto> {
  return apiFetch<FunnelDto>(`/api/v1/laces/${laceId}/funnel`)
}

/** A person at one of the Lace's target accounts. */
export interface ContactDto {
  id: string
  account_id: string
  account_name: string
  name: string | null
  title: string | null
  email: string | null
  linkedin: string | null
  source: "discovery" | "contact_search" | "founder"
  /** When the founder cleared them for outreach: drafts go only to approved people. */
  approved_at: string | null
  first_seen_at: string
}

export function setLaceContactApproved(laceId: string, contactId: string, approved: boolean): Promise<ContactDto> {
  return apiFetch(`/api/v1/laces/${laceId}/contacts/${contactId}`, { method: "PATCH", body: JSON.stringify({ approved }) })
}

/** Ask the Lace to draft a first message to one person (approving them),
 * with the founder's note. The draft lands in Messaging. */
export function draftToLaceContact(laceId: string, contactId: string, channel: "email" | "linkedin",
                                   note: string): Promise<{ run_id: string }> {
  return apiFetch(`/api/v1/laces/${laceId}/contacts/${contactId}/draft`, {
    method: "POST", body: JSON.stringify({ channel, note: note.trim() || null }),
  })
}

/** Clear everyone found at one account for outreach. */
export function approveLaceAccountContacts(laceId: string, accountId: string): Promise<{ approved: number }> {
  return apiFetch(`/api/v1/laces/${laceId}/accounts/${accountId}/contacts/approve`, { method: "POST" })
}

export function listLaceContacts(laceId: string): Promise<ContactDto[]> {
  return apiFetch<ContactDto[]>(`/api/v1/laces/${laceId}/contacts`)
}

/** Look for who to contact at one account; the Lace reports back when done. */
export function findLaceAccountContacts(laceId: string, accountId: string): Promise<{ run_id: string }> {
  return apiFetch(`/api/v1/laces/${laceId}/accounts/${accountId}/find-contacts`, { method: "POST" })
}

export type LaceSearchKind = "lace" | "fact" | "competitor" | "account" | "contact" | "opportunity" | "conversation"

/** One thing found by a search across the founder's Laces. */
export interface LaceSearchHitDto {
  kind: LaceSearchKind
  id: string
  title: string
  subtitle: string | null
  lace_id: string
  lace_name: string
}

/** Shorter queries are not searched (the server refuses them). */
export const LACE_SEARCH_MIN_LENGTH = 2

export function searchLaces(q: string, signal?: AbortSignal): Promise<LaceSearchHitDto[]> {
  return apiFetch<LaceSearchHitDto[]>(`/api/v1/laces/search?q=${encodeURIComponent(q)}`, { signal })
}
