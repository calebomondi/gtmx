import type { ContactDto, LaceOutreachDto, OutreachChannel } from "@/lib/api"

import { isUnread } from "./outreach-threads"

/** Where a person can be written to, best first. */
const REACH_ORDER: OutreachChannel[] = ["email", "linkedin", "x", "instagram", "facebook", "tiktok"]

export interface Reach {
  channel: OutreachChannel
  /** An email address, or their profile URL on that platform. */
  address: string
}

/** Each way to reach a person that is on file, best first. */
export function reachOf(contact: ContactDto): Reach[] {
  return REACH_ORDER.flatMap((channel) => {
    const address = contact[channel]
    return address ? [{ channel, address }] : []
  })
}

/** Contacts whose name, title, account or email holds `query`. */
export function filterContacts(contacts: ContactDto[], query: string): ContactDto[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return contacts
  return contacts.filter((c) => [c.name, c.title, c.account_name, c.email]
    .some((field) => field?.toLowerCase().includes(needle)))
}

export interface AccountContacts {
  accountId: string
  accountName: string
  people: ContactDto[]
  /** Not yet cleared for outreach. */
  waiting: number
}

/** Contacts by account, in the order they come (by account, then name). */
export function byAccount(contacts: ContactDto[]): AccountContacts[] {
  const groups = new Map<string, AccountContacts>()
  for (const c of contacts) {
    const group = groups.get(c.account_id) ?? { accountId: c.account_id, accountName: c.account_name, people: [], waiting: 0 }
    group.people.push(c)
    if (!c.approved_at) group.waiting += 1
    groups.set(c.account_id, group)
  }
  return [...groups.values()]
}

/** People at one account not yet cleared for outreach. */
export function waitingAt(contacts: ContactDto[], accountId: string): number {
  return contacts.filter((c) => c.account_id === accountId && !c.approved_at).length
}

/** Everything sent to, drafted for or received from one person, oldest first. */
export function messagesWith(outreach: LaceOutreachDto[], contact: ContactDto): LaceOutreachDto[] {
  const addresses = reachOf(contact).map((r) => r.address.toLowerCase())
  return outreach
    .filter((m) => (m.recipient_address && addresses.includes(m.recipient_address.toLowerCase()))
      || (contact.name && m.recipient_name === contact.name && m.recipient_company === contact.account_name))
    .sort((a, b) => (a.sent_at ?? a.created_at).localeCompare(b.sent_at ?? b.created_at))
}

/** Their replies the founder has not opened, counted by channel. */
export function unreadByChannel(outreach: LaceOutreachDto[], contact: ContactDto): Partial<Record<OutreachChannel, number>> {
  const counts: Partial<Record<OutreachChannel, number>> = {}
  for (const m of messagesWith(outreach, contact)) {
    if (isUnread(m)) counts[m.channel] = (counts[m.channel] ?? 0) + 1
  }
  return counts
}

export function unreadTotal(counts: Partial<Record<OutreachChannel, number>>): number {
  return Object.values(counts).reduce((sum, n) => sum + (n ?? 0), 0)
}

/** People with new replies first, and their accounts before the rest; the
 * order is otherwise kept. */
export function byNewReplies(groups: AccountContacts[],
                             unread: ReadonlyMap<string, Partial<Record<OutreachChannel, number>>>): AccountContacts[] {
  const fresh = (c: ContactDto) => unreadTotal(unread.get(c.id) ?? {}) > 0
  const first = <T,>(items: T[], ahead: (item: T) => boolean) => [...items.filter(ahead), ...items.filter((i) => !ahead(i))]
  return first(groups.map((g) => ({ ...g, people: first(g.people, fresh) })), (g) => g.people.some(fresh))
}
