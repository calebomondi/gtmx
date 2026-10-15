// Types for the competitor endpoints come from the competition module rather
// than being redeclared here, so the client shape and the render shape cannot
// drift into two definitions of the same company.
import type {
  Competitor,
  CompetitorList,
  CompetitorRun,
  CompetitorRunStart,
} from '@/features/competition/competition-types'
import { apiFetch } from "./http"

// ---------------------------------------------------------------------------
// Competitors
// ---------------------------------------------------------------------------
// Seven endpoints, and two of them are on `/runs` rather than `/{id}`. The
// literal path segments are declared first on the server for the same reason —
// a `/{competitor_id}` route would otherwise shadow them for any method that
// accepts a path param. The order here does not matter, but keeping the run
// endpoints grouped apart from the item endpoints does.

/** Start a competitor hunt.
 *
 * 202 rather than 200 when a run is already in flight: the server reuses the
 * pending run instead of starting a second one, so the response's `run` is not
 * necessarily the one this call began. `already_tracked` is how many rows this
 * run found were already on the list. */
export function startCompetitorRun(
  workspaceId: string,
): Promise<CompetitorRunStart> {
  return apiFetch<CompetitorRunStart>(
    `/api/v1/workspaces/${workspaceId}/competitors/runs`,
    { method: "POST" },
  )
}

export function getCompetitorRun(
  workspaceId: string,
  runId: string,
): Promise<CompetitorRun> {
  return apiFetch<CompetitorRun>(
    `/api/v1/workspaces/${workspaceId}/competitors/runs/${runId}`,
  )
}

export function listCompetitorRuns(
  workspaceId: string,
  limit = 20,
): Promise<CompetitorRun[]> {
  return apiFetch<CompetitorRun[]>(
    `/api/v1/workspaces/${workspaceId}/competitors/runs?limit=${limit}`,
  )
}

export function listCompetitors(workspaceId: string): Promise<CompetitorList> {
  return apiFetch<CompetitorList>(
    `/api/v1/workspaces/${workspaceId}/competitors`,
  )
}

/** Add a competitor by URL and let the agent derive the rest.
 *
 * `deep_research: false` skips the follow-up site read, for the case where the
 * user just wants the row on the list. It returns 200 rather than 201 when the
 * company is already tracked — the resource was not created, and a caller
 * treating 201 as "this is new" would show a false confirmation. */
export function addCompetitor(
  workspaceId: string,
  input: { website: string; name?: string; deep_research?: boolean },
): Promise<Competitor> {
  return apiFetch<Competitor>(
    `/api/v1/workspaces/${workspaceId}/competitors`,
    { method: "POST", body: JSON.stringify(input) },
  )
}

/** Edit a competitor.
 *
 * Narrow on purpose: the request schema is `extra="forbid"` and carries only
 * user-owned fields plus `notes`. A client cannot write `strengths` or
 * `pricing` here, so an edit from this tab cannot replace researched findings
 * with invented ones. */
export function updateCompetitor(
  workspaceId: string,
  competitorId: string,
  patch: {
    name?: string | null
    website?: string | null
    target_customers?: string | null
    headquarters?: string | null
    geography_scope?: string | null
    notes?: string | null
  },
): Promise<Competitor> {
  return apiFetch<Competitor>(
    `/api/v1/workspaces/${workspaceId}/competitors/${competitorId}`,
    { method: "PATCH", body: JSON.stringify(patch) },
  )
}

export function deleteCompetitor(
  workspaceId: string,
  competitorId: string,
): Promise<void> {
  return apiFetch<void>(
    `/api/v1/workspaces/${workspaceId}/competitors/${competitorId}`,
    { method: "DELETE" },
  )
}

/** Re-check every tracked competitor now; changes arrive as feed signals. */
export function checkCompetitorsNow(workspaceId: string): Promise<import("./runs").RunDto> {
  return apiFetch(`/api/v1/workspaces/${workspaceId}/competitors/monitor`, { method: "POST" })
}
