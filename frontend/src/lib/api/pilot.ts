import { apiFetch } from "./http"

/** Whether the app is in its closed pilot; public, for the sign-up page. */
export function getPilotStatus(): Promise<{ invite_only: boolean }> {
  return apiFetch("/api/v1/pilot")
}
