import { apiFetch } from "./http"

export type RunStatus =
  | "pending"
  | "running"
  | "awaiting_input"
  | "completed"
  | "failed"
  | "cancelled"

export interface RunDto {
  id: string
  kind: string
  status: RunStatus
  workspace_id: string | null
  progress: Record<string, unknown> | null
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

/** The signed-in user's unfinished runs, newest first. */
export function listActiveRuns(): Promise<RunDto[]> {
  return apiFetch<RunDto[]>("/api/v1/runs/active")
}

export function answerRun(runId: string, answer: string): Promise<void> {
  return apiFetch<void>(`/api/v1/runs/${runId}/answer`, {
    method: "POST",
    body: JSON.stringify({ answer }),
  })
}

export function cancelRun(runId: string): Promise<RunDto> {
  return apiFetch<RunDto>(`/api/v1/runs/${runId}/cancel`, { method: "POST" })
}
