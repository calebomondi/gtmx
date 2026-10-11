import type { SearchHitDto, SearchKind } from "@/lib/api"

/** The workspace tab each kind of hit lives on. */
const TAB: Partial<Record<SearchKind, string>> = {
  competitor: "competition",
  account: "outreach",
  signal: "feed",
}

/** Where selecting a hit goes. Archived workspaces open read-only. */
export function hitPath(hit: SearchHitDto): string {
  if (hit.kind === "project") return hit.archived ? "/archive" : `/projects/${hit.id}`
  const workspaceId = hit.workspace_id ?? hit.id
  if (hit.archived) return `/archive/workspace/${workspaceId}`
  const tab = TAB[hit.kind]
  return `/workspace/${workspaceId}${tab ? `?tab=${tab}` : ""}`
}

export const KIND_LABELS: Record<SearchKind, string> = {
  workspace: "Workspaces",
  project: "Projects",
  competitor: "Competitors",
  account: "Accounts",
  signal: "Feed",
}
