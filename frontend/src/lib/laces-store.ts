import { useSyncExternalStore } from "react"

import type { LaceState } from "@/components/lace-mascot"
import {
  archiveLace as archiveLaceApi,
  deleteLace as deleteLaceApi,
  listArchivedLaces,
  listLaces,
  restoreLace as restoreLaceApi,
  updateLace,
  type LaceDto,
  type LaceListItemDto,
} from "@/lib/api"
import { supabase } from "@/lib/supabase"

export interface LacesState {
  laces: LaceListItemDto[]
  archived: LaceDto[]
  loading: boolean
  /** True once a fetch has finished, so an empty list means "no Laces". */
  loaded: boolean
  error: string | null
}

type Listener = () => void

const listeners = new Set<Listener>()

let state: LacesState = { laces: [], archived: [], loading: false, loaded: false, error: null }

function setState(patch: Partial<LacesState>): void {
  state = { ...state, ...patch }
  for (const listener of listeners) listener()
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): LacesState {
  return state
}

export function useLaces(): LacesState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

export async function refetchLaces(): Promise<void> {
  setState({ loading: true, error: null })
  try {
    const { data } = await supabase.auth.getSession()
    const [laces, archived] = data.session ? await Promise.all([listLaces(), listArchivedLaces()]) : [[], []]
    setState({ laces, archived, loading: false, loaded: true })
  } catch (err) {
    setState({ loading: false, error: err instanceof Error ? err.message : String(err) })
  }
}

/** Fetch if we have never fetched; refetch triggers are explicit elsewhere. */
export function ensureLacesLoaded(): void {
  if (!state.loaded && !state.loading) void refetchLaces()
}

function patchLace(laceId: string, patch: Partial<LaceListItemDto>): void {
  setState({ laces: state.laces.map((lace) => (lace.id === laceId ? { ...lace, ...patch } : lace)) })
}

export async function toggleLacePin(laceId: string): Promise<void> {
  const lace = state.laces.find((item) => item.id === laceId)
  if (!lace) return
  patchLace(laceId, { pinned: !lace.pinned })
  try {
    await updateLace(laceId, { pinned: !lace.pinned })
  } catch (err) {
    patchLace(laceId, { pinned: lace.pinned })
    setState({ error: err instanceof Error ? err.message : String(err) })
    throw err
  }
}

/** Archive, restore or delete a Lace, then reload both lists (a restored
 * Lace comes back with its mood). Errors are the caller's to show. */
export async function archiveLace(laceId: string): Promise<LaceDto> {
  const lace = await archiveLaceApi(laceId)
  await refetchLaces()
  return lace
}

export async function restoreLace(laceId: string): Promise<LaceDto> {
  const lace = await restoreLaceApi(laceId)
  await refetchLaces()
  return lace
}

export async function deleteLace(laceId: string): Promise<void> {
  await deleteLaceApi(laceId)
  await refetchLaces()
}

/** The mascot a Lace shows in the sidebar. Its mood when something is going
 * on (working, or waiting on the founder); otherwise by place: every pinned
 * Lace looks alert, and in the full list the first is alert, the second idle
 * and the rest sleepy. The list is most recently active first, so the place
 * follows activity too. */
export function sidebarMascot(lace: LaceListItemDto, section: "pinned" | "all", index: number): LaceState {
  if (lace.mood) return lace.mood
  if (section === "pinned" || index === 0) return "alert"
  return index === 1 ? "idle" : "sleepy"
}
