import type { LaceState } from "@/components/lace-mascot"

/** A Lace's places: what it found (Feed), the chat with it, reaching
 * people (Outreach: email, and LinkedIn notes the founder sends), and the
 * founder's own social accounts (Social). Outreach keeps its "messaging"
 * key so links into it keep working. */
export type LaceTab = "feed" | "chat" | "messaging" | "social"

export const LACE_TABS: readonly LaceTab[] = ["feed", "chat", "messaging", "social"]

export const LACE_TAB_LABELS: Record<LaceTab, string> = { feed: "Feed", chat: "Chat", messaging: "Outreach", social: "Social" }

/** The chat button's mascot: thinking while the Lace works on a reply,
 * alert while the chat is open, idle otherwise. */
export function chatMascot(tab: LaceTab, working: boolean): LaceState {
  if (working) return "thinking"
  return tab === "chat" ? "alert" : "idle"
}
