import { useState } from "react"
import { BookOpen, Building2, Sparkles, Swords, Users, type LucideIcon } from "lucide-react"

import type { FeedTarget } from "./lace-activity-actions"
import type { LaceChat } from "./use-lace-chat"
import type { LaceOpportunities } from "./use-lace-opportunities"

export interface FoundItem {
  id: string
  label: string
  /** When it was found or learned. */
  at: string
  /** Found by a search and waiting for the founder to save or dismiss it. */
  suggested?: boolean
}

export interface FoundSection {
  key: string
  title: string
  icon: LucideIcon
  items: FoundItem[]
  /** How many wait on the founder (to review, to approve). */
  waiting: number
  waitingLabel: string
  open: () => void
  /** Sent to the Lace when the section is empty, to start on it. */
  ask: string
}

export function newestFirst(items: FoundItem[]): FoundItem[] {
  return [...items].sort((a, b) => b.at.localeCompare(a.at))
}

/** Everything the Lace has learned and found, gathered as the chat goes. */
export function foundSections(chat: LaceChat, opps: LaceOpportunities, open: (target: FeedTarget) => void,
                              openKnowledge: () => void): FoundSection[] {
  return [
    {
      key: "knows", title: "What it knows", icon: BookOpen, waiting: 0, waitingLabel: "", open: openKnowledge,
      ask: "What did you learn about us from our website?",
      items: chat.facts.map((f) => ({ id: f.id, label: f.claim, at: f.recorded_at })),
    },
    {
      key: "competitors", title: "Competitors", icon: Swords, waiting: chat.suggestedCompetitors.length,
      waitingLabel: "to review", open: () => open({ tab: "feed", section: "competitors" }),
      ask: "Who are my competitors?",
      items: [...chat.suggestedCompetitors.map((c) => ({ id: c.id, label: c.name, at: c.first_seen_at, suggested: true })),
              ...chat.competitors.map((c) => ({ id: c.id, label: c.name, at: c.first_seen_at }))],
    },
    {
      key: "customers", title: "Customers", icon: Building2, waiting: chat.suggestedAccounts.length,
      waitingLabel: "to review", open: () => open({ tab: "feed", section: "accounts" }),
      ask: "Find target accounts for us",
      items: [...chat.suggestedAccounts.map((a) => ({ id: a.id, label: a.name, at: a.first_seen_at, suggested: true })),
              ...chat.accounts.map((a) => ({ id: a.id, label: a.name, at: a.first_seen_at }))],
    },
    {
      key: "opportunities", title: "Opportunities", icon: Sparkles, waiting: opps.suggested.length,
      waitingLabel: "to review", open: () => open({ tab: "feed", section: "opportunities" }),
      ask: "Find opportunities for us",
      items: [...opps.suggested.map((o) => ({ id: o.id, label: o.title, at: o.first_seen_at, suggested: true })),
              ...opps.opportunities.map((o) => ({ id: o.id, label: o.title, at: o.first_seen_at }))],
    },
    {
      key: "contacts", title: "Contacts", icon: Users, waiting: chat.contacts.filter((c) => !c.approved_at).length,
      waitingLabel: "to approve", open: () => open({ tab: "messaging", section: "contacts" }),
      ask: "Find who to contact at our saved accounts",
      items: chat.contacts.map((c) => ({
        id: c.id, label: [c.name ?? c.email ?? "Someone", c.account_name].join(" · "), at: c.first_seen_at,
      })),
    },
  ]
}

/** How many items arrived after `since`, across every section. */
export function newCount(sections: FoundSection[], since: number): number {
  return sections.reduce((n, s) => n + s.items.filter((i) => Date.parse(i.at) > since).length, 0)
}


/** When the Lace was opened: finds after it count as new. */
export function useOpenedAt(): number {
  const [openedAt] = useState(() => Date.now())
  return openedAt
}
