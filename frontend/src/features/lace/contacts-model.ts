import type { ContactDto, LaceOutreachDto, OutreachChannel } from "@/lib/api"

import { isUnread } from "./outreach-threads"

/** Where a person can be written to, best first. */
// The ways a contact's record holds to reach them; Telegram isn't one (a bot can't start a chat).
const REACH_ORDER: Exclude<OutreachChannel, "telegram">[] = ["email", "linkedin", "x", "instagram", "facebook", "tiktok"]

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

/** What a person does and where, e.g. "Founder & CEO, Synnefa". */
export function roleAt(contact: ContactDto): string {
  return [contact.title?.trim(), contact.account_name].filter(Boolean).join(", ")
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

/** People with new replies first; the order is otherwise kept (by account,
 * then name, as the API lists them). */
export function byNewReplies(contacts: ContactDto[],
                             unread: ReadonlyMap<string, Partial<Record<OutreachChannel, number>>>): ContactDto[] {
  const fresh = (c: ContactDto) => unreadTotal(unread.get(c.id) ?? {}) > 0
  return [...contacts.filter(fresh), ...contacts.filter((c) => !fresh(c))]
}
