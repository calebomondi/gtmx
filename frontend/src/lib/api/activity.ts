import { apiFetch } from "./http"

export interface HeartbeatDto {
  next_beat_s: number
}

/** "The user is active, on this workspace if any." The server decides how
 * much time the ping is worth. */
export function sendHeartbeat(workspaceId: string | null): Promise<HeartbeatDto> {
  return apiFetch<HeartbeatDto>("/api/v1/activity/heartbeat", {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId }),
  })
}
