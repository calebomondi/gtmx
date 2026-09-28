import { useSyncExternalStore } from "react"

import { getWorkspaceInsights, type WorkspaceInsights } from "@/lib/api"

export interface InsightsState {
  insights: WorkspaceInsights | null
  loading: boolean
  error: string | null
}

type Listener = () => void

const listeners = new Set<Listener>()
const states = new Map<string, InsightsState>()

const EMPTY_STATE: InsightsState = {
  insights: null,
  loading: false,
  error: null,
}

function notify(): void {
  for (const listener of listeners) listener()
}

function stateFor(workspaceId: string | undefined): InsightsState {
  if (!workspaceId) return EMPTY_STATE
  return states.get(workspaceId) ?? EMPTY_STATE
}

function setState(workspaceId: string, patch: Partial<InsightsState>): void {
  const previous = states.get(workspaceId) ?? EMPTY_STATE
  states.set(workspaceId, { ...previous, ...patch })
  notify()
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Fetch (or re-fetch) the persisted insights for a workspace. */
export async function refreshInsights(workspaceId: string): Promise<void> {
  setState(workspaceId, { loading: true, error: null })
  try {
    const insights = await getWorkspaceInsights(workspaceId)
    setState(workspaceId, { insights, loading: false, error: null })
  } catch (err) {
    setState(workspaceId, {
      loading: false,
      error: err instanceof Error ? err.message : String(err),
    })
  }
}

/** Fetch on first mount for a workspace; later refreshes are explicit. */
export function ensureInsightsLoaded(workspaceId: string | undefined): void {
  if (!workspaceId) return
  if (!states.has(workspaceId)) {
    void refreshInsights(workspaceId)
  }
}

export function useInsights(workspaceId: string | undefined): InsightsState {
  return useSyncExternalStore(
    subscribe,
    () => stateFor(workspaceId),
    () => stateFor(workspaceId),
  )
}
