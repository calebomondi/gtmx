import type { ActivityDto, ActivityKind } from "@/lib/api"

import type { LaceTab } from "./lace-tabs"

/** The Feed's sub-tabs. */
export type FeedSection = "activity" | "opportunities" | "accounts" | "competitors"
export const FEED_SECTIONS: readonly FeedSection[] = ["activity", "opportunities", "accounts", "competitors"]

/** Messaging's sub-tabs. */
export type MessagingSection = "conversations" | "people" | "inboxes"
export const MESSAGING_SECTIONS: readonly MessagingSection[] = ["conversations", "people", "inboxes"]

export type LaceSection = FeedSection | MessagingSection

export interface FeedTarget {
  tab: LaceTab
  section?: LaceSection
}

/** Where each kind of activity takes the founder, and what the button says. */
export const ACTIVITY_ACTIONS: Record<ActivityKind, { label: string; target: FeedTarget }> = {
  brief: { label: "Read in chat", target: { tab: "chat" } },
  competitors_found: { label: "See competitors", target: { tab: "feed", section: "competitors" } },
  competitor_moves: { label: "See competitors", target: { tab: "feed", section: "competitors" } },
  accounts_found: { label: "See accounts", target: { tab: "feed", section: "accounts" } },
  contacts_found: { label: "See accounts", target: { tab: "feed", section: "accounts" } },
  drafts_ready: { label: "Review drafts", target: { tab: "messaging", section: "conversations" } },
  reply_received: { label: "Read the reply", target: { tab: "messaging", section: "conversations" } },
  opportunities_found: { label: "See opportunities", target: { tab: "feed", section: "opportunities" } },
  job_failed: { label: "Talk it through", target: { tab: "chat" } },
}

export interface NeedsYouItem {
  label: string
  target: FeedTarget
}

/** What waits on the founder, for the strip at the top of the Feed: what
 * searches found to save or dismiss, people to approve for outreach,
 * messages to send or read, and searches
 * that stopped for something only the founder can give (unseen until this
 * visit). */
export function needsYou(waiting: number, failedSearches: ActivityDto[],
                         suggestions: Partial<Record<FeedSection, number>> = {}, toApprove = 0): NeedsYouItem[] {
  const items: NeedsYouItem[] = []
  if (toApprove > 0) {
    items.push({ label: `${toApprove} ${toApprove === 1 ? "person" : "people"} to approve for outreach`,
                 target: { tab: "messaging", section: "people" } })
  }
  const toReview = Object.values(suggestions).reduce((sum, n) => sum + (n ?? 0), 0)
  const first = FEED_SECTIONS.find((section) => suggestions[section])
  if (toReview > 0 && first) {
    items.push({ label: `${toReview} ${toReview === 1 ? "suggestion" : "suggestions"} to review`,
                 target: { tab: "feed", section: first } })
  }
  if (waiting > 0) {
    items.push({ label: `${waiting} ${waiting === 1 ? "message waits" : "messages wait"} on you`,
                 target: { tab: "messaging", section: "conversations" } })
  }
  if (failedSearches.length > 0) {
    const n = failedSearches.length
    items.push({ label: `${n} ${n === 1 ? "search needs" : "searches need"} your input`, target: { tab: "chat" } })
  }
  return items
}

/** The URL hash that opens a sub-tab, e.g. /lace/:id/feed#accounts. */
export function sectionHash(section: LaceSection): string {
  return `#${section}`
}

/** The sub-tab a URL hash opens, if it names one of `sections`. */
export function sectionFromHash<S extends LaceSection>(hash: string, sections: readonly S[]): S | null {
  const name = hash.replace(/^#/, "")
  return (sections as readonly string[]).includes(name) ? (name as S) : null
}
