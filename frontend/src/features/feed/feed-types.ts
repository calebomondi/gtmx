import type { SignalInsight } from '@/lib/api'

export type SignalCategory =
  | 'inbound'
  | 'outbound'
  | 'competitor'
  | 'market'
  | 'product'
  | 'agent'
  | 'opportunity'

export type SignalActionKind =
  | 'reply'
  | 'outreach'
  | 'source'
  | 'dismiss'
  | 'mute'

export interface SignalSender {
  name: string
  email: string
  avatar: string
  company?: string
}

export interface SignalAction {
  kind: SignalActionKind
  label: string
}

export interface Signal {
  id: string
  category: SignalCategory
  title: string
  entity: string
  summary: string
  body?: string
  subject?: string
  timestamp: number
  read: boolean
  pinned: boolean
  hot: boolean
  reason: string
  insight?: SignalInsight
  sender?: SignalSender
  sourceUrl?: string
  actions: SignalAction[]
}

export type RecencyFilter = '24hr' | '7d' | '30d' | '90d'

export type CategoryFilter = 'all' | SignalCategory

export const RECENCY_MS: Record<RecencyFilter, number> = {
  '24hr': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
  '90d': 90 * 24 * 60 * 60 * 1000,
}

export function formatTimeAgo(timestamp: number): string {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`
  return `${Math.floor(months / 12)}y ago`
}

export function isRecent(signal: Signal, filter: RecencyFilter): boolean {
  return Date.now() - signal.timestamp <= RECENCY_MS[filter]
}