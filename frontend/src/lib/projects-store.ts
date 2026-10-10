import { useSyncExternalStore } from "react"

import {
  archiveProject,
  createProject as createProjectApi,
  deleteProject as deleteProjectApi,
  getCurrentUser,
  listProjects,
  renameProject as renameProjectApi,
  reorderProjects as reorderProjectsApi,
  restoreProject as restoreProjectApi,
  type ProjectDto,
} from "@/lib/api"
import { refetchWorkspaces } from "@/lib/workspaces-store"
import { supabase } from "@/lib/supabase"

export interface ProjectsState {
  /** Live projects, bucketed by `priority` (does not include archived). */
  projects: ProjectDto[]
  /** Archived projects, for the /archive page. */
  archivedProjects: ProjectDto[]
  loading: boolean
  error: string | null
}

type Listener = () => void

const listeners = new Set<Listener>()

let state: ProjectsState = {
  projects: [],
  archivedProjects: [],
  loading: false,
  error: null,
}

function setState(patch: Partial<ProjectsState>): void {
  state = { ...state, ...patch }
  for (const listener of listeners) listener()
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): ProjectsState {
  return state
}

export function useProjects(): ProjectsState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

export async function refetchProjects(): Promise<void> {
  setState({ loading: true, error: null })
  try {
    const { data } = await supabase.auth.getSession()
    if (!data.session) {
      setState({ projects: [], archivedProjects: [], loading: false, error: null })
      return
    }
    const user = await getCurrentUser()
    const [projects, archivedProjects] = await Promise.all([
      listProjects(user.id),
      listProjects(user.id, true),
    ])
    setState({ projects, archivedProjects, loading: false, error: null })
  } catch (err) {
    setState({
      loading: false,
      error: err instanceof Error ? err.message : String(err),
    })
  }
}

export function ensureProjectsLoaded(): void {
  if (state.projects.length === 0 && state.archivedProjects.length === 0 && !state.loading) {
    void refetchProjects()
  }
}

function resetOrder(projects: ProjectDto[]): void {
  setState({ projects, error: null })
}

export async function createProject(name: string): Promise<ProjectDto> {
  const user = await getCurrentUser()
  const created = await createProjectApi(user.id, name)
  await refetchProjects()
  return created
}

export async function renameProject(projectId: string, name: string): Promise<void> {
  const previous = state.projects
  await renameProjectApi(projectId, name)
  try {
    await refetchProjects()
  } catch (err) {
    setState({ projects: previous, error: err instanceof Error ? err.message : String(err) })
    throw err
  }
}

/**
 * Persist the two-bucket drag order. Applies the new order optimistically so
 * the columns re-render instantly; rolls back by refetching on failure.
 */
export async function reorderProjects(
  priority: string[],
  other: string[],
): Promise<void> {
  const previous = state.projects
  const byId = new Map(state.projects.map((project) => [project.id, project]))
  const placed = (id: string, priority: boolean, index: number): ProjectDto | null => {
    const project = byId.get(id)
    return project ? { ...project, priority, position: index } : null
  }
  const reordered = [
    ...priority.map((id, index) => placed(id, true, index)),
    ...other.map((id, index) => placed(id, false, index)),
  ].filter((entry): entry is ProjectDto => entry !== null)
  resetOrder(reordered)
  try {
    const user = await getCurrentUser()
    await reorderProjectsApi(user.id, priority, other)
  } catch (err) {
    setState({ projects: previous, error: err instanceof Error ? err.message : String(err) })
    throw err
  }
}

async function withUserRefetch(
  action: (user: { id: string }) => Promise<unknown>,
): Promise<void> {
  const user = await getCurrentUser()
  await action(user)
  await Promise.all([refetchProjects(), refetchWorkspaces()])
}

/** Archive a project; the server auto-archives every member workspace. */
export async function archiveProjectAction(projectId: string): Promise<void> {
  await withUserRefetch(() => archiveProject(projectId))
}

/** Restore a project (and all of its member workspaces). */
export async function restoreProjectAction(projectId: string): Promise<void> {
  await withUserRefetch(() => restoreProjectApi(projectId))
}

export async function deleteProjectAction(projectId: string): Promise<void> {
  await withUserRefetch(() => deleteProjectApi(projectId))
}