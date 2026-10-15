import { apiFetch } from "./http"
import type {
  CompetitionDataDto,
  IcpDto,
  IdealCompetitorProfileDto,
  MarketDataDto,
  OfferSnapshot,
  SpecialistDto,
} from "./discovery"

export interface WorkspaceSummary {
  id: string
  user_id: string
  name: string | null
  pinned: boolean
  product_name: string | null
  offer_type: "product" | "service" | null
  project_id: string | null
  archived: boolean
  archived_at: string | null
  date_created: string
  last_activity: string
}

export function workspaceDisplayName(workspace: WorkspaceSummary): string {
  return workspace.name?.trim() || workspace.product_name?.trim() || "Untitled workspace"
}

export function listWorkspaces(
  userId: string,
  archived = false,
): Promise<WorkspaceSummary[]> {
  return apiFetch<WorkspaceSummary[]>(
    `/api/v1/workspaces/user/${userId}${archived ? "?archived=true" : ""}`,
  )
}

export interface ProductFeatureDto {
  id: string
  name: string
  description: string | null
  differentiator: string | null
}

export interface ProductProfileDto {
  id: string
  workspace_id: string
  product_name: string | null
  product_url: string | null
  product_description: string | null
  intent: string | null
  problem_solved: string | null
  how_it_works: string | null
  target_geo: string[]
  confirmed: boolean
  features: ProductFeatureDto[]
}

/** Full workspace (includes archived ones); `product_profile` is eager-loaded. */
export interface WorkspaceDetail extends WorkspaceSummary {
  product_profile: ProductProfileDto | null
}

export function getWorkspace(workspaceId: string): Promise<WorkspaceDetail> {
  return apiFetch<WorkspaceDetail>(`/api/v1/workspaces/${workspaceId}`)
}

export function updateWorkspace(
  workspaceId: string,
  body: { name?: string; pinned?: boolean; project_id?: string | null },
): Promise<WorkspaceSummary> {
  return apiFetch<WorkspaceSummary>(`/api/v1/workspaces/${workspaceId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

export function deleteWorkspace(workspaceId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/workspaces/${workspaceId}`, {
    method: "DELETE",
  })
}

export function archiveWorkspace(workspaceId: string): Promise<WorkspaceSummary> {
  return apiFetch<WorkspaceSummary>(`/api/v1/workspaces/${workspaceId}/archive`, {
    method: "POST",
  })
}

export function restoreWorkspace(workspaceId: string): Promise<WorkspaceSummary> {
  return apiFetch<WorkspaceSummary>(`/api/v1/workspaces/${workspaceId}/restore`, {
    method: "POST",
  })
}

/** Final discovery-run results persisted server-side when the run completes. */
export interface WorkspaceInsights {
  offer_snapshot: OfferSnapshot | null
  /** Asserted at intake, not classified by the agent. Persisted because the
   * competitor agent runs later from the workspace and hunts in this noun. */
  offer_type: 'product' | 'service' | null
  confirmed: boolean
  domain_understanding: string | null
  market_fit_understanding: string | null
  market_data: MarketDataDto | null
  competition_data: CompetitionDataDto | null
  /** Persisted beside the SWOD so a reload still has the stage's primary output.
   * The competitors tab reads it; the competitor agent consumes it server-side. */
  ideal_competitor_profile: IdealCompetitorProfileDto | null
  icp: IcpDto | null
  specialists: SpecialistDto[] | null
  completed_at: string | null
}

export function getWorkspaceInsights(
  workspaceId: string,
): Promise<WorkspaceInsights | null> {
  return apiFetch<{ insights: WorkspaceInsights | null }>(
    `/api/v1/workspaces/${workspaceId}/insights`,
  ).then((body) => body.insights)
}
