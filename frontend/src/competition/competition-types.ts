export type TrackingSourceKind =
  | 'website'
  | 'linkedin'
  | 'x'
  | 'github'
  | 'other'

export interface TrackingSource {
  kind: TrackingSourceKind
  value: string
}

export interface PainSignal {
  pain: string
  evidence: string
  source_url: string | null
}

export interface Competitor {
  name: string
  description: string
  website: string | null
  tracking_sources: TrackingSource[]
  offering: string | null
  positioning: string | null
  comparison: string | null
  business_model: string | null
  pricing: string | null
  target_customers: string | null
  notable_customers: string[]
  strengths: string[]
  weaknesses: string[]
  whats_unique: string | null
  pain_signals: PainSignal[]
  deep_researched_at: string | null
}

export interface CompetitionState {
  competitors: Competitor[]
  strengths: string[]
  weaknesses: string[]
  opportunities: string[]
  differentiators: string[]
}

export const TRACKING_KIND_LABELS: Record<TrackingSourceKind, string> = {
  website: 'Website',
  linkedin: 'LinkedIn',
  x: 'X / Twitter',
  github: 'GitHub',
  other: 'Other',
}

export const TRACKING_KINDS: TrackingSourceKind[] = [
  'website',
  'linkedin',
  'x',
  'github',
  'other',
]