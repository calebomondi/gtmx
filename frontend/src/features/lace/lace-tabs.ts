import type { LaceState } from "@/components/lace-mascot"

/** A Lace's places: what it found (Feed), the chat with it, reaching out
 * (Messaging), and the founder's apps it works in (Apps). */
export type LaceTab = "feed" | "chat" | "messaging" | "apps"

export const LACE_TABS: readonly LaceTab[] = ["feed", "chat", "messaging", "apps"]

/** The chat button's mascot: thinking while the Lace works on a reply,
 * alert while the chat is open, idle otherwise. */
export function chatMascot(tab: LaceTab, working: boolean): LaceState {
  if (working) return "thinking"
  return tab === "chat" ? "alert" : "idle"
}
