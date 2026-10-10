import { apiFetch } from "./http"
import type { WorkspaceSummary } from "./workspaces"

export interface ProjectDto {
  id: string
  user_id: string
  name: string
  name_key: string
  priority: boolean
  position: number
  archived: boolean
  archived_at: string | null
  date_created: string
  last_activity: string
  workspace_count: number
  archived_workspace_count: number
}

export interface ProjectDetailDto extends ProjectDto {
  workspaces: WorkspaceSummary[]
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export function listProjects(
  userId: string,
  archived = false,
): Promise<ProjectDto[]> {
  return apiFetch<ProjectDto[]>(
    `/api/v1/projects/user/${userId}${archived ? "?archived=true" : ""}`,
  )
}

export function createProject(userId: string, name: string): Promise<ProjectDto> {
  return apiFetch<ProjectDto>(`/api/v1/projects/user/${userId}`, {
    method: "POST",
    body: JSON.stringify({ name }),
  })
}

export function getProject(projectId: string): Promise<ProjectDetailDto> {
  return apiFetch<ProjectDetailDto>(`/api/v1/projects/${projectId}`)
}

export function renameProject(projectId: string, name: string): Promise<ProjectDto> {
  return apiFetch<ProjectDto>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  })
}

/** Persist the two-bucket drag order (`priority` / `other` = project ids). */
export function reorderProjects(
  userId: string,
  priority: string[],
  other: string[],
): Promise<void> {
  return apiFetch<void>(`/api/v1/projects/user/${userId}/order`, {
    method: "PUT",
    body: JSON.stringify({ priority, other }),
  })
}

export function archiveProject(projectId: string): Promise<ProjectDetailDto> {
  return apiFetch<ProjectDetailDto>(`/api/v1/projects/${projectId}/archive`, {
    method: "POST",
  })
}

export function restoreProject(projectId: string): Promise<ProjectDetailDto> {
  return apiFetch<ProjectDetailDto>(`/api/v1/projects/${projectId}/restore`, {
    method: "POST",
  })
}

export function deleteProject(projectId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/projects/${projectId}`, {
    method: "DELETE",
  })
}
