import { MAX_EVENTS_PER_BATCH, recordEvents, type EventDto, type EventName } from "@/lib/api"

// Events wait this long to go together, unless a batch fills first. Short:
// sending as the page closes can't wait for a token, so whatever is still
// queued then (the last page someone saw before leaving, say) can be lost.
const FLUSH_AFTER_MS = 2_000
// The backend caps details at this.
const DETAIL_CHARS = 64

const queue: EventDto[] = []
let timer: ReturnType<typeof setTimeout> | null = null

function flush() {
  if (timer) clearTimeout(timer)
  timer = null
  while (queue.length > 0) {
    // Best effort: a batch that can't be sent (offline, signed out) is let go
    // rather than retried, so counting usage never gets in the user's way.
    void recordEvents(queue.splice(0, MAX_EVENTS_PER_BATCH)).catch(() => undefined)
  }
}

if (typeof window !== "undefined") {
  // Before the tab goes into the background, reloads or closes, send what's waiting.
  document.addEventListener("visibilitychange", () => document.visibilityState === "hidden" && flush())
  window.addEventListener("pagehide", flush)
}

/** Note that the user did something, for the admin dashboard's view of how
 * the app is used. Names come from a fixed list; never put message text or
 * contact details in `detail`. */
export function track(name: EventName, { detail = null, laceId = null }: { detail?: string | null; laceId?: string | null } = {}) {
  queue.push({ name, detail: detail?.slice(0, DETAIL_CHARS) ?? null, lace_id: laceId, at: new Date().toISOString() })
  if (queue.length >= MAX_EVENTS_PER_BATCH) flush()
  else timer ??= setTimeout(flush, FLUSH_AFTER_MS)
}
