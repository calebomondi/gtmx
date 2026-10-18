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
  created_at: string
}

export interface FactDto {
  id: string
  topic: FactTopic
  claim: string
  source_url: string | null
  confidence: "high" | "medium" | "low"
  origin: "crawl" | "research" | "user" | "monitor"
  recorded_at: string
}

export interface LaceMessageDto {
  role: "founder" | "lace"
  content: string
}

/** The browser's IANA timezone, e.g. "Africa/Nairobi": when the founder's day starts. */
export function localTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone
}

export function createLace(name: string, website: string): Promise<{ lace: LaceDto; run_id: string }> {
  return apiFetch("/api/v1/laces", { method: "POST", body: JSON.stringify({ name, website, timezone: localTimeZone() }) })
}

export function listLaces(): Promise<LaceDto[]> {
  return apiFetch<LaceDto[]>("/api/v1/laces")
}

export function getLace(laceId: string): Promise<LaceDto> {
  return apiFetch<LaceDto>(`/api/v1/laces/${laceId}`)
}

export function listLaceFacts(laceId: string): Promise<FactDto[]> {
  return apiFetch<FactDto[]>(`/api/v1/laces/${laceId}/facts`)
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
