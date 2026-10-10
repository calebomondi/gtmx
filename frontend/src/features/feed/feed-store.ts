import { useEffect, useSyncExternalStore } from 'react'

import { listSignals, updateSignal, type SignalChanges, type SignalDto } from '@/lib/api'

import type { HomeSignal } from '@/features/home-feed/home-feed-types'
import type { SignalAction, SignalCategory } from './feed-types'

/**
 * The feed, loaded from the server: one cache per view (a workspace id, or
 * "all" for the home feed). Signals are emitted server-side by agent runs; the
 * user only reads, pins and dismisses them, which is applied optimistically
 * and written back.
 */

const ALL = 'all'
const REFRESH_MS = 30_000
const EMPTY: HomeSignal[] = []

const caches = new Map<string, HomeSignal[]>()
const listeners = new Set<() => void>()

function notify(): void {
  for (const listener of listeners) listener()
}

function actionsFor(dto: SignalDto): SignalAction[] {
  const actions: SignalAction[] = []
  if (dto.source_url) actions.push({ kind: 'source', label: 'View source' })
  actions.push({ kind: 'dismiss', label: 'Dismiss' })
  return actions
}

function toSignal(dto: SignalDto): HomeSignal {
  return {
    id: dto.id,
    category: dto.category as SignalCategory,
    title: dto.title,
    entity: dto.entity,
    summary: dto.summary,
    body: dto.body ?? undefined,
    reason: dto.reason,
    sourceUrl: dto.source_url ?? undefined,
    timestamp: Date.parse(dto.created_at),
    read: dto.read,
    pinned: dto.pinned,
    hot: dto.hot,
    actions: actionsFor(dto),
    workspace: { id: dto.workspace_id, name: dto.workspace_name ?? 'Untitled workspace' },
  }
}

async function load(key: string): Promise<void> {
  try {
    const dtos = await listSignals(key === ALL ? undefined : key)
    caches.set(key, dtos.map(toSignal))
    notify()
  } catch {
    // keep what we had; the next refresh retries
  }
}

/** Apply a change in every cached view now, persist it, and refetch on failure. */
function change(id: string, changes: SignalChanges, apply: (signal: HomeSignal) => HomeSignal | null): void {
  for (const [key, signals] of caches) {
    caches.set(key, signals.flatMap((s) => {
      if (s.id !== id) return [s]
      const next = apply(s)
      return next ? [next] : []
    }))
  }
  notify()
  updateSignal(id, changes).catch(() => {
    for (const key of caches.keys()) void load(key)
  })
}

export function markRead(id: string): void {
  change(id, { read: true }, (s) => ({ ...s, read: true }))
}

export function togglePin(id: string): void {
  let pinned = false
  for (const signals of caches.values()) {
    const found = signals.find((s) => s.id === id)
    if (found) pinned = !found.pinned
  }
  change(id, { pinned }, (s) => ({ ...s, pinned }))
}

export function dismiss(id: string): void {
  change(id, { dismissed: true }, () => null)
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** One workspace's feed, or every workspace's when `workspaceId` is omitted.
 * Loads on mount and refreshes while mounted. */
export function useSignals(workspaceId?: string): HomeSignal[] {
  const key = workspaceId ?? ALL
  useEffect(() => {
    void load(key)
    const timer = window.setInterval(() => void load(key), REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [key])
  return useSyncExternalStore(subscribe, () => caches.get(key) ?? EMPTY)
}
