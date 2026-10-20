import type { LaceSearchHitDto, LaceSearchKind } from "@/lib/api"

import { sectionHash, type LaceSection } from "./lace-activity-actions"

export const SEARCH_KIND_LABELS: Record<LaceSearchKind, string> = {
  lace: "Laces",
  fact: "What your Laces know",
  competitor: "Competitors",
  account: "Accounts",
  contact: "Contacts",
  opportunity: "Opportunities",
  conversation: "Conversations",
}

const SECTIONS: Partial<Record<LaceSearchKind, LaceSection>> = {
  competitor: "competitors",
  account: "accounts",
  opportunity: "opportunities",
  contact: "people",
  conversation: "conversations",
}

/** Where a hit opens: its Lace, on the tab and sub-tab that holds it. */
export function hitPath(hit: LaceSearchHitDto): string {
  const base = `/lace/${hit.lace_id}`
  const section = SECTIONS[hit.kind]
  const tab = hit.kind === "contact" || hit.kind === "conversation" ? "messaging" : "feed"
  return section ? `${base}/${tab}${sectionHash(section)}` : `${base}/feed`
}
