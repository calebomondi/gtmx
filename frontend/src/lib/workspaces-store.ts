import { useSyncExternalStore } from "react"

import {
  listWorkspaces,
  updateWorkspace,
  deleteWorkspace,
  archiveWorkspace,
  restoreWorkspace,
  getCurrentUser,
  type WorkspaceSummary,
} from "@/lib/api"
import { supabase } from "@/lib/supabase"

export interface WorkspacesState {
  workspaces: WorkspaceSummary[]
  archivedWorkspaces: WorkspaceSummary[]
  loading: boolean
  error: string | null
}

type Listener = () => void

const listeners = new Set<Listener>()

let state: WorkspacesState = {
  workspaces: [],
  archivedWorkspaces: [],
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
    const { data } = await supabase.auth.getSession()
    if (!data.session) {
      setState({ workspaces: [], archivedWorkspaces: [], loading: false, error: null })
      return
    }
    const user = await getCurrentUser()
    const [workspaces, archivedWorkspaces] = await Promise.all([
      listWorkspaces(user.id),
      listWorkspaces(user.id, true),
    ])
    setState({
      workspaces,
      archivedWorkspaces,
      loading: false,
      error: null,
    })
  } catch (err) {
    setState({
      loading: false,
      error: err instanceof Error ? err.message : String(err),
    })
  }
}

/** Fetch if we have never fetched; refetch triggers are explicit elsewhere. */
export function ensureWorkspacesLoaded(): void {
  if (
    state.workspaces.length === 0 &&
    state.archivedWorkspaces.length === 0 &&
    !state.loading
  ) {
    void refetchWorkspaces()
  }
}

function patchWorkspace(
  workspaceId: string,
  patch: Partial<WorkspaceSummary>,
): void {
  // Patch both lists: an archived workspace still needs to reflect renames,
  // and archive/restore move a row between them.
  const apply = (workspace: WorkspaceSummary) =>
    workspace.id === workspaceId ? { ...workspace, ...patch } : workspace
  setState({
    workspaces: state.workspaces.map(apply),
    archivedWorkspaces: state.archivedWorkspaces.map(apply),
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

async function withWorkspacePatch(
  workspaceId: string,
  patch: Partial<WorkspaceSummary>,
  request: () => Promise<unknown>,
): Promise<void> {
  const previous = { ...state }
  patchWorkspace(workspaceId, patch)
  try {
    await request()
  } catch (err) {
    setState({
      ...previous,
      error: err instanceof Error ? err.message : String(err),
    })
    throw err
  }
}

/** Add a workspace to a project (existing membership is replaced). */
export async function addToProject(
  workspaceId: string,
  projectId: string,
): Promise<void> {
  await withWorkspacePatch(workspaceId, { project_id: projectId }, () =>
    updateWorkspace(workspaceId, { project_id: projectId }),
  )
}

/** Unlink a workspace from its project (remains a normal ungrouped workspace). */
export async function removeFromProject(workspaceId: string): Promise<void> {
  await withWorkspacePatch(workspaceId, { project_id: null }, () =>
    updateWorkspace(workspaceId, { project_id: null }),
  )
}

/** Move a workspace between the live and archived lists, optimistically. */
function moveWorkspace(workspaceId: string, toArchived: boolean): void {
  const from = toArchived ? state.workspaces : state.archivedWorkspaces
  const workspace = from.find((item) => item.id === workspaceId)
  if (!workspace) return
  const stamped: WorkspaceSummary = {
    ...workspace,
    archived: toArchived,
    archived_at: toArchived
      ? (workspace.archived_at ?? new Date().toISOString())
      : null,
  }
  const without = (list: WorkspaceSummary[]) =>
    list.filter((item) => item.id !== workspaceId)
  setState({
    workspaces: toArchived
      ? without(state.workspaces)
      : [...without(state.workspaces), stamped],
    archivedWorkspaces: toArchived
      ? [...without(state.archivedWorkspaces), stamped]
      : without(state.archivedWorkspaces),
  })
}

/** Archive a workspace: hidden from feeds/lists, excluded from agent tracking. */
export async function archiveWorkspaceAction(workspaceId: string): Promise<void> {
  const previous = { ...state }
  moveWorkspace(workspaceId, true)
  try {
    await archiveWorkspace(workspaceId)
    await refetchWorkspaces()
  } catch (err) {
    setState({
      ...previous,
      error: err instanceof Error ? err.message : String(err),
    })
    throw err
  }
}

/** Restore an archived workspace back into the live list. */
export async function restoreWorkspaceAction(workspaceId: string): Promise<void> {
  const previous = { ...state }
  moveWorkspace(workspaceId, false)
  try {
    await restoreWorkspace(workspaceId)
    await refetchWorkspaces()
  } catch (err) {
    setState({
      ...previous,
      error: err instanceof Error ? err.message : String(err),
    })
    throw err
  }
}

/** Permanently delete an archived workspace (also handles a live one). */
export async function deleteArchivedWorkspace(workspaceId: string): Promise<void> {
  try {
    await deleteWorkspace(workspaceId)
    setState({
      workspaces: state.workspaces.filter((item) => item.id !== workspaceId),
      archivedWorkspaces: state.archivedWorkspaces.filter(
        (item) => item.id !== workspaceId,
      ),
      error: null,
    })
  } catch (err) {
    setState({ error: err instanceof Error ? err.message : String(err) })
    throw err
  }
}
