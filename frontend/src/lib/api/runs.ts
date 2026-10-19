import { apiFetch, apiStream } from "./http"

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
  lace_id: string | null
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

export function getRun(runId: string): Promise<RunDto> {
  return apiFetch<RunDto>(`/api/v1/runs/${runId}`)
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

/** One progress step a long run reported ("Searching: direct substitutes"). */
export interface RunStepDto {
  /** Cursor: pass the last one as `after` to get only newer steps. */
  id: number
  text: string
  created_at: string
}

export function listRunSteps(runId: string, after = 0): Promise<RunStepDto[]> {
  return apiFetch<RunStepDto[]>(`/api/v1/runs/${runId}/steps?after=${after}`)
}

/** One frame a run emitted. `type` decides which other fields are present. */
export interface RunFrame {
  type: string
  event_id: number
  run_id: string
  text?: string
  message?: string
  content?: string
  role?: string
  tool?: string
  ok?: boolean
  summary?: string
  /** "progress" frames: how far onboarding has got, 0 to 1. */
  fraction?: number
  /** "onboarded" frames: the pages onboarding could read. */
  pages_read?: string[]
}

/** Every frame of a run after `after`: the backlog, then live, ending after
 * the run's terminal frame ("complete", "error" or "cancelled"). */
export function followRunEvents(
  runId: string,
  onFrame: (frame: RunFrame) => void,
  { after = 0, signal }: { after?: number; signal?: AbortSignal } = {},
): Promise<void> {
  return apiStream<RunFrame>(`/api/v1/runs/${runId}/events?after=${after}`, onFrame, signal)
}
