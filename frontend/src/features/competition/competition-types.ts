// Types for the Competitors tab.
//
// These mirror the backend's CompetitorResponse / CompetitorRunResponse
// field for field, and deliberately so. The old versions here were written
// against a `Competitor` shape that nothing ever persisted — the tab's list
// came from the agent's SWOD extraction, which carried no names, so the list
// was always empty and the shape was never exercised against real data. Now
// that rows exist, the client type is the API contract rather than a guess,
// and a drift between the two shows up as a type error instead of as a field
// that silently renders blank.

/** The networks a competitor can be tracked on.
 *
 * `instagram` and `tiktok` were added with the agent: the brief asks for them
 * explicitly, and most competitors' most active channel is one of the two. The
 * backend's `TrackingSource.kind` is an open string, so this list is the
 * *rendering* set -- an unrecognised kind still renders, under "Other", rather
 * than being dropped. A competitor's only social should never be invisible
 * because we did not think of the network. */
export type TrackingSourceKind =
  | 'website'
  | 'instagram'
  | 'tiktok'
  | 'x'
  | 'linkedin'
  | 'github'
  | 'other'

export const TRACKING_KIND_LABELS: Record<TrackingSourceKind, string> = {
  website: 'Website',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  x: 'X / Twitter',
  linkedin: 'LinkedIn',
  github: 'GitHub',
  other: 'Other',
}

export const TRACKING_KINDS: TrackingSourceKind[] = [
  'website',
  'linkedin',
  'instagram',
  'tiktok',
  'x',
  'github',
  'other',
]

/** How sure we are a social handle belongs to *this* company.
 *
 * A handle found next to a company name in a directory is not the same claim as
 * one read off the company's own site, and conflating them is how a user ends
 * up following a different business. */
export type Confidence = 'high' | 'medium' | 'low'

export interface TrackingSource {
  kind: TrackingSourceKind | string
  value: string
  confidence?: Confidence | null
}

export interface SocialPost {
  text: string
  url: string | null
  date: string | null
  likes: number | null
}

/** Live stats for one network, normalized server-side from Bright Data.
 * Counts are null when the network hides them -- never shown as zero. */
export interface SocialProfile {
  platform: string
  url: string
  name: string | null
  followers: number | null
  posts_count: number | null
  likes: number | null
  employees: string | null
  verified: boolean
  bio: string | null
  recent_posts: SocialPost[]
  fetched_at: string | null
}

/** One claim about a real company, with the evidence for it.
 *
 * Strengths, weaknesses, pain signals and customer sentiment are all this type
 * rather than one per category: the categories differ in what the agent may do
 * with them, not in how a claim is stored. `evidence` is not optional because
 * the alternative — a claim with no quote behind it — is a guess, and the whole
 * point of this tab is that it does not contain any. The agent's
 * `SourcedFinding` requires it upstream, so reaching a claim without evidence
 * means the source is not one of ours. */
export interface SourcedClaim {
  text: string
  evidence: string
  source_url: string | null
}

/** Per-category source URLs, keyed by field name.
 *
 * `evidence.weaknesses` is the list of pages the weaknesses were read from.
 * Kept as a map rather than only as per-claim `source_url` because the two
 * answer different questions: the per-claim URL says where *this line* came
 * from, the map says how much of the company's site was read at all. A firm
 * with three weaknesses all citing one page is a thinner read than one citing
 * three, and only the map shows that. */
export type EvidenceMap = Record<string, string[]>

export interface Competitor {
  id: string
  workspace_id: string
  /** The run that first found this company. Null for a manually added one. */
  run_id: string | null
  name: string
  /** Never null and never empty: the backend enforces the brief's rule that a
   * competitor without a public website is not a competitor. */
  website: string
  /** The normalised host, unique per workspace. This is what dedup runs on,
   * not `website`, so `acme.com` and `https://www.acme.com/about` are one row. */
  domain_key: string
  description: string | null
  offering: string | null
  positioning: string | null
  business_model: string | null
  pricing: string | null
  target_customers: string | null
  headquarters: string | null
  /** local | regional | global | any, when known. */
  geography_scope: string | null
  comparison: string | null
  /** Which archetype of the ideal profile this company matched. */
  matched_archetype: string | null
  strengths: SourcedClaim[]
  weaknesses: SourcedClaim[]
  /** Plain strings, unlike the four sourced lists: an opportunity is a claim
   * about *us* derived from facts about them, not a quote from anyone. */
  opportunities: string[]
  notable_customers: string[]
  pain_signals: SourcedClaim[]
  customer_sentiment: SourcedClaim[]
  tracking_sources: TrackingSource[]
  evidence: EvidenceMap | null
  /** Fields research could not establish, by name.
   *
   * The honest record, and the reason this tab can say "not found" instead of
   * rendering a dash that reads as "nothing to report". An empty list means
   * everything was established; a long one means the profile is thin, and the
   * two must not look alike. */
  unsourced_fields: string[]
  /** The user's own words about this competitor. Never overwritten by the
   * agent — a later run refreshes the research but leaves this alone. */
  notes: string | null
  /** agent | manual. A manual row stays manual across every later run. */
  source: 'agent' | 'manual'
  first_seen_at: string
  last_seen_at: string
  /** When monitoring last re-checked this rival; null if never. */
  last_checked_at: string | null
  /** Keyed by platform (linkedin | x | instagram | tiktok); null until the
   * first monitoring run has fetched them. */
  social_profiles: Record<string, SocialProfile> | null
  socials_checked_at: string | null
  deep_researched_at: string | null
}

/** The competition stage's SWOD, and the only thing this tab reads from it.
 *
 * It used to also carry `competitors`, the agent's extracted rival names. That
 * field is gone from the agent, and it is not replaced by the archetype
 * profile: archetypes are a construct, and rendering them in a list of real
 * tracked companies would be indistinguishable from a fabricated one. */
export interface CompetitionSwod {
  strengths: string[]
  weaknesses: string[]
  opportunities: string[]
  differentiators: string[]
}

export type CompetitorRunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'

export interface CompetitorRun {
  id: string
  workspace_id: string
  status: CompetitorRunStatus
  error: string | null
  /** Everything the search surfaced, before the website filter. */
  candidates_seen: number
  /** What survived and landed on the watch list. */
  found: number
  /** What was cut, with `dropped_reasons` saying why.
   *
   * Reported rather than hidden because the two outcomes look identical from
   * the list alone: "searched 40 firms and kept 3" is the filter working, and
   * "found 3" is a thin search. Only the counts tell them apart. */
  dropped: number
  dropped_reasons: Record<string, number> | null
  profile_confidence: string | null
  archetypes_targeted: number
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface CompetitorRunStart {
  run: CompetitorRun
  /** Rows this run found that were already tracked, i.e. refreshed rather
   * than added. Non-zero means a re-run found nothing new, which is worth
   * saying out loud rather than showing as an empty result. */
  already_tracked: number
}

export interface CompetitorList {
  competitors: Competitor[]
  total: number
}

/** Human labels for the drop reasons the agent's screen records.
 *
 * Falls back to the raw key for anything unrecognised: the reason is the
 * user-facing explanation for a company *not* being on their list, so a new
 * reason must read as something rather than as an underscore-joined token. */
export const DROP_REASON_LABELS: Record<string, string> = {
  no_public_website:
    'no public website — the brief requires one, so there was nothing to verify against',
  is_the_offer_itself: 'this is your own company',
  directory_or_social_url:
    'the link was a directory or social profile, not the company’s own site',
  duplicate: 'already on the list under another URL spelling',
  self_domain_alias: 'another spelling of a domain you already track',
}

export function dropReasonLabel(reason: string): string {
  return (
    DROP_REASON_LABELS[reason] ??
    reason.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
  )
}

/** Labels for `unsourced_fields`, so the UI can say what is missing by name
 * rather than showing a raw column key. */
export const UNSOURCED_FIELD_LABELS: Record<string, string> = {
  description: 'description',
  offering: 'what they sell',
  positioning: 'positioning',
  business_model: 'business model',
  pricing: 'pricing',
  target_customers: 'who they serve',
  headquarters: 'headquarters',
  geography_scope: 'where they operate',
  comparison: 'how they compare to you',
  matched_archetype: 'which archetype',
  strengths: 'strengths',
  weaknesses: 'weaknesses',
  opportunities: 'opportunities for you',
  notable_customers: 'notable customers',
  pain_signals: 'customer pain signals',
  customer_sentiment: 'what customers say',
  tracking_sources: 'socials',
  identity: 'confirming the website belongs to them',
}

export function unsourcedFieldLabel(field: string): string {
  return (
    UNSOURCED_FIELD_LABELS[field] ?? field.replace(/_/g, ' ')
  )
}