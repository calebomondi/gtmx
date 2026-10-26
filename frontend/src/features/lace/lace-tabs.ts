import type { LaceState } from "@/components/lace-mascot"

/** A Lace's three places: what it found (Feed), the chat with it, and
 * reaching out (Messaging). */
export type LaceTab = "feed" | "chat" | "messaging"

export const LACE_TABS: readonly LaceTab[] = ["feed", "chat", "messaging"]

export const LACE_TAB_LABELS: Record<LaceTab, string> = { feed: "Feed", chat: "Chat", messaging: "Messaging" }

/** The chat button's mascot: thinking while the Lace works on a reply,
 * alert while the chat is open, idle otherwise. */
export function chatMascot(tab: LaceTab, working: boolean): LaceState {
  if (working) return "thinking"
  return tab === "chat" ? "alert" : "idle"
}
