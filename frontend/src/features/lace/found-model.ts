import { Building2, Sparkles, Swords, Users, type LucideIcon } from "lucide-react"

import type { FeedTarget } from "./lace-activity-actions"
import type { LaceChat } from "./use-lace-chat"
import type { LaceOpportunities } from "./use-lace-opportunities"

export interface FoundItem {
  id: string
  label: string
  detail?: string | null
  /** When it was found. */
  at: string
  /** Waits on the founder: a suggestion to save or dismiss, a contact to approve. */
  waiting: boolean
}

export interface FoundSection {
  key: "competitors" | "leads" | "opportunities" | "contacts"
  title: string
  /** One of them, for "+1 competitor". */
  noun: string
  icon: LucideIcon
  /** Newest first. */
  items: FoundItem[]
  waitingLabel: string
  open: () => void
  /** Sent to the Lace when there is nothing yet, to start on it. */
  ask: string
  /** For a waiting item: keep it (save, approve) or drop it. */
  keep: (id: string) => void
  keepLabel: string
  drop?: (id: string) => void
}

function newestFirst(items: FoundItem[]): FoundItem[] {
  return [...items].sort((a, b) => b.at.localeCompare(a.at))
}

/** What the Lace has found as the chat goes, by kind, each with what waits on
 * the founder and how to act on it in place. */
export function foundSections(chat: LaceChat, opps: LaceOpportunities, open: (target: FeedTarget) => void): FoundSection[] {
  return [
    {
      key: "competitors", title: "Competitors", noun: "competitor", icon: Swords, waitingLabel: "to review",
      open: () => open({ tab: "feed", section: "competitors" }), ask: "Who are my competitors?",
      keep: (id) => void chat.saveCompetitor(id), keepLabel: "Track", drop: (id) => void chat.dismissCompetitor(id),
      items: newestFirst([
        ...chat.suggestedCompetitors.map((c) => ({ id: c.id, label: c.name, detail: c.summary, at: c.first_seen_at, waiting: true })),
        ...chat.competitors.map((c) => ({ id: c.id, label: c.name, detail: c.summary, at: c.first_seen_at, waiting: false })),
      ]),
    },
    {
      key: "leads", title: "Leads", noun: "lead", icon: Building2, waitingLabel: "to review",
      open: () => open({ tab: "feed", section: "accounts" }), ask: "Find leads for us",
      keep: (id) => void chat.saveAccount(id), keepLabel: "Save", drop: (id) => void chat.dismissAccount(id),
      items: newestFirst([
        ...chat.suggestedAccounts.map((a) => ({ id: a.id, label: a.name, detail: a.trigger?.event, at: a.first_seen_at, waiting: true })),
        ...chat.accounts.map((a) => ({ id: a.id, label: a.name, detail: a.trigger?.event, at: a.first_seen_at, waiting: false })),
      ]),
    },
    {
      key: "opportunities", title: "Opportunities", noun: "opportunity", icon: Sparkles, waitingLabel: "to review",
      open: () => open({ tab: "feed", section: "opportunities" }), ask: "Find opportunities for us",
      keep: (id) => void opps.save(id), keepLabel: "Save", drop: (id) => void opps.dismiss(id),
      items: newestFirst([
        ...opps.suggested.map((o) => ({ id: o.id, label: o.title, detail: o.organiser, at: o.first_seen_at, waiting: true })),
        ...opps.opportunities.map((o) => ({ id: o.id, label: o.title, detail: o.organiser, at: o.first_seen_at, waiting: false })),
      ]),
    },
    {
      key: "contacts", title: "Contacts", noun: "contact", icon: Users, waitingLabel: "to approve",
      open: () => open({ tab: "messaging", section: "contacts" }), ask: "Find who to contact at our saved accounts",
      keep: (id) => void chat.approveContact(id, true), keepLabel: "Approve",
      items: newestFirst(chat.contacts.map((c) => ({
        id: c.id, label: c.name ?? c.email ?? "Someone", detail: [c.title, c.account_name].filter(Boolean).join(" · "),
        at: c.first_seen_at, waiting: !c.approved_at,
      }))),
    },
  ]
}

export function isNewSince(item: FoundItem, since: number): boolean {
  return Date.parse(item.at) > since
}
