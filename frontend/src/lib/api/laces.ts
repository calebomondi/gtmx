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
  question: string
  options: string[]
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
}

export type UiBlockDto = ChoicesBlockDto | CardBlockDto

export interface LaceMessageDto {
  role: "founder" | "lace"
  content: string
  /** Cards and choices under a Lace reply. */
  ui?: UiBlockDto[]
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
export function sendLaceMessage(laceId: string, text: string): Promise<{ run_id: string }> {
  return apiFetch(`/api/v1/laces/${laceId}/messages`, { method: "POST", body: JSON.stringify({ text }) })
}

export type CompetitorStatus = "tracked" | "dismissed"

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

export function setLaceCompetitorStatus(laceId: string, competitorId: string, status: CompetitorStatus): Promise<LaceCompetitorDto> {
  return apiFetch(`/api/v1/laces/${laceId}/competitors/${competitorId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  })
}

export type AccountStatus = "target" | "dismissed"

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

export function setLaceAccountStatus(laceId: string, accountId: string, status: AccountStatus): Promise<LaceAccountDto> {
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
  status: "open" | "dismissed"
  first_seen_at: string
}

/** Open opportunities (none past their deadline or date), soonest first. */
export function listLaceOpportunities(laceId: string): Promise<LaceOpportunityDto[]> {
  return apiFetch<LaceOpportunityDto[]>(`/api/v1/laces/${laceId}/opportunities`)
}

export function dismissLaceOpportunity(laceId: string, opportunityId: string): Promise<LaceOpportunityDto> {
  return apiFetch(`/api/v1/laces/${laceId}/opportunities/${opportunityId}`, {
    method: "PATCH", body: JSON.stringify({ status: "dismissed" }),
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
  source: "discovery" | "contact_search"
  first_seen_at: string
}

export function listLaceContacts(laceId: string): Promise<ContactDto[]> {
  return apiFetch<ContactDto[]>(`/api/v1/laces/${laceId}/contacts`)
}

/** Look for who to contact at one account; the Lace reports back when done. */
export function findLaceAccountContacts(laceId: string, accountId: string): Promise<{ run_id: string }> {
  return apiFetch(`/api/v1/laces/${laceId}/accounts/${accountId}/find-contacts`, { method: "POST" })
}
