import type { LaceSearchHitDto, LaceSearchKind } from "@/lib/api"

import { sectionId, type FeedSection } from "./lace-activity-actions"

export const SEARCH_KIND_LABELS: Record<LaceSearchKind, string> = {
  lace: "Laces",
  fact: "What your Laces know",
  competitor: "Competitors",
  account: "Accounts",
  contact: "Contacts",
  opportunity: "Opportunities",
  conversation: "Conversations",
}

const FEED_SECTIONS: Partial<Record<LaceSearchKind, FeedSection>> = {
  competitor: "competitors",
  account: "accounts",
  opportunity: "opportunities",
}

/** Where a hit opens: its Lace, on the tab (and Feed section) that holds it. */
export function hitPath(hit: LaceSearchHitDto): string {
  const base = `/lace/${hit.lace_id}`
  if (hit.kind === "contact" || hit.kind === "conversation") return `${base}/messaging`
  const section = FEED_SECTIONS[hit.kind]
  return section ? `${base}/feed#${sectionId(section)}` : `${base}/feed`
}
