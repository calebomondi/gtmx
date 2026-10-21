import type { LaceListItemDto } from "@/lib/api"

/** How much of the backdrop a page gets: chat keeps it quiet so the
 * conversation stays the focus. */
export type BackdropTone = "full" | "calm"

/** What the backdrop's mood line says: a Lace needs the founder, is working,
 * or is idle. */
export type BackdropMood = "alert" | "thinking" | "idle"

const CHAT_PATH = /^\/lace\/[^/]+\/chat\/?$/
const LACE_PATH = /^\/lace\/([^/]+)/

export function backdropTone(pathname: string): BackdropTone {
  return CHAT_PATH.test(pathname) ? "calm" : "full"
}

/** On a Lace's pages, that Lace's mood; elsewhere, the most pressing of all
 * of them (one needing the founder beats one working). */
export function backdropMood(pathname: string, laces: readonly LaceListItemDto[]): BackdropMood {
  const laceId = LACE_PATH.exec(pathname)?.[1]
  const moods = (laceId ? laces.filter((lace) => lace.id === laceId) : laces).map((lace) => lace.mood)
  if (moods.includes("alert")) return "alert"
  if (moods.includes("thinking")) return "thinking"
  return "idle"
}
