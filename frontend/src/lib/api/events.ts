import { apiFetch } from "./http"

/** Mirrors backend/app/schemas/events.py EventName: add a name in both. */
export type EventName =
  | "page_viewed"
  | "setup_phase"
  | "lace_settings_opened"
  | "lace_people_opened"
  | "chat_thread_switched"
  | "quick_ask_used"
  | "contact_opened"
  | "search_opened"
  | "feedback_opened"

/** Mirrors MAX_EVENTS_PER_BATCH. */
export const MAX_EVENTS_PER_BATCH = 50

export interface EventDto {
  name: EventName
  detail: string | null
  lace_id: string | null
  /** When it happened, by this browser's clock. */
  at: string
}

export function recordEvents(events: EventDto[]): Promise<{ recorded: number }> {
  // keepalive: a batch sent as the page closes still arrives.
  return apiFetch("/api/v1/events", { method: "POST", body: JSON.stringify({ events }), keepalive: true })
}
