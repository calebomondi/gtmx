import type { ContactDto, OutreachChannel } from "@/lib/api"

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
