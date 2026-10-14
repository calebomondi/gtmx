import { apiFetch } from "./http"

export interface SignalInsight {
  means: string
  next_move: string
}

export interface SignalDto {
  id: string
  workspace_id: string
  workspace_name: string | null
  run_id: string | null
  category: string
  title: string
  entity: string
  summary: string
  body: string | null
  reason: string
  /** What the item means for the user and the move to make. */
  insight: SignalInsight | null
  source_url: string | null
  hot: boolean
  read: boolean
  pinned: boolean
  created_at: string
}

export interface SignalChanges {
  read?: boolean
  pinned?: boolean
  dismissed?: boolean
}

/** The feed, newest first: one workspace, or every workspace when omitted. */
export function listSignals(workspaceId?: string): Promise<SignalDto[]> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : ""
  return apiFetch<SignalDto[]>(`/api/v1/signals${query}`)
}

export function updateSignal(signalId: string, changes: SignalChanges): Promise<SignalDto> {
  return apiFetch<SignalDto>(`/api/v1/signals/${signalId}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  })
}
