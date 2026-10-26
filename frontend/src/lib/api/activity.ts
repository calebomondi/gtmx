import { apiFetch } from "./http"

export interface HeartbeatDto {
  next_beat_s: number
}

/** "The user is active." The server decides how much time the ping is worth. */
export function sendHeartbeat(): Promise<HeartbeatDto> {
  return apiFetch<HeartbeatDto>("/api/v1/activity/heartbeat", { method: "POST" })
}
