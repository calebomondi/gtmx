import { useSyncExternalStore } from "react"

import {
  listWorkspaces,
  updateWorkspace,
  deleteWorkspace,
  getCurrentUser,
  type WorkspaceSummary,
} from "@/lib/api"

export interface WorkspacesState {
  workspaces: WorkspaceSummary[]
  loading: boolean
  error: string | null
}

type Listener = () => void

const listeners = new Set<Listener>()

let state: WorkspacesState = {
  workspaces: [],
  loading: false,
  error: null,
}

function setState(patch: Partial<WorkspacesState>): void {
  state = { ...state, ...patch }
  for (const listener of listeners) listener()
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): WorkspacesState {
  return state
}

export function useWorkspaces(): WorkspacesState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

export async function refetchWorkspaces(): Promise<void> {
  setState({ loading: true, error: null })
  try {
    const user = await getCurrentUser()
    const workspaces = await listWorkspaces(user.id)
    setState({ workspaces, loading: false, error: null })
  } catch (err) {
    setState({
      loading: false,
      error: err instanceof Error ? err.message : String(err),
    })
  }
}

/** Fetch if we have never fetched; refetch triggers are explicit elsewhere. */
export function ensureWorkspacesLoaded(): void {
  if (state.workspaces.length === 0 && !state.loading) {
    void refetchWorkspaces()
  }
}

function patchWorkspace(
  workspaceId: string,
  patch: Partial<WorkspaceSummary>,
): void {
  setState({
    workspaces: state.workspaces.map((workspace) =>
      workspace.id === workspaceId ? { ...workspace, ...patch } : workspace,
    ),
  })
}

export async function renameWorkspace(
  workspaceId: string,
  name: string,
): Promise<void> {
  const previous = state.workspaces
  patchWorkspace(workspaceId, { name })
  try {
    const updated = await updateWorkspace(workspaceId, { name })
    patchWorkspace(workspaceId, updated)
  } catch (err) {
    setState({
      workspaces: previous,
      error: err instanceof Error ? err.message : String(err),
    })
    throw err
  }
}

export async function toggleWorkspacePin(workspaceId: string): Promise<void> {
  const workspace = state.workspaces.find((item) => item.id === workspaceId)
  if (!workspace) return
  const pinned = !workspace.pinned
  patchWorkspace(workspaceId, { pinned })
  try {
    const updated = await updateWorkspace(workspaceId, { pinned })
    patchWorkspace(workspaceId, updated)
  } catch (err) {
    patchWorkspace(workspaceId, { pinned: workspace.pinned })
    setState({ error: err instanceof Error ? err.message : String(err) })
    throw err
  }
}

export async function removeWorkspace(workspaceId: string): Promise<void> {
  const previous = state.workspaces
  setState({
    workspaces: state.workspaces.filter((item) => item.id !== workspaceId),
  })
  try {
    await deleteWorkspace(workspaceId)
  } catch (err) {
    setState({
      workspaces: previous,
      error: err instanceof Error ? err.message : String(err),
    })
    throw err
  }
}
