import { apiFetch } from "./http"

/** Mirrors backend/app/schemas/feedback.py FEEDBACK_MAX_CHARS. */
export const FEEDBACK_MAX_CHARS = 2000

/** Send the team a suggestion or a problem, with the page (and Lace) it came from. */
export function sendFeedback(text: string, path: string, laceId: string | null): Promise<{ id: string; created_at: string }> {
  return apiFetch("/api/v1/feedback", { method: "POST", body: JSON.stringify({ text, path, lace_id: laceId }) })
}
