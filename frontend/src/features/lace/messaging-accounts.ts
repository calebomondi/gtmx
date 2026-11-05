import { MAILBOXES, type ConnectionDto, type LaceAppDto, type LaceOutreachDto, type Mailbox } from "@/lib/api"
import { PLATFORM_LABEL, type Platform } from "@/lib/platforms"

import { OUTREACH_CHANNELS, waitsOnFounder } from "./outreach-threads"

/** Which account Outreach shows: every one, a mailbox's email, or LinkedIn. */
export type AccountKey = "all" | Mailbox | "linkedin"

/** Platforms Outreach offers to connect, in order: mailboxes, and LinkedIn for notes the founder sends. */
export const MESSAGING_PLATFORMS: Platform[] = [...MAILBOXES, "linkedin"]

export interface MessagingAccount {
  key: Exclude<AccountKey, "all">
  platform: Platform
  label: string
  /** Who the account is (an address or @handle), when known. */
  detail: string | null
  /** connected: live; attention: connected but needs signing in again; none:
   * messages on it, but it isn't connected (any more). */
  state: "connected" | "attention" | "none"
  /** Drafts and unread replies on it. */
  waiting: number
  /** The mailbox new email goes from. */
  sends: boolean
}

/** The mailbox an email is in. One sent before mailboxes were recorded went
 * the way a Lace picked then: Gmail when connected, else Outlook. */
export function mailboxOf(message: LaceOutreachDto, apps: LaceAppDto[]): Mailbox {
  if (message.mailbox) return message.mailbox
  return apps.some((a) => a.platform === "gmail" && a.connected) ? "gmail" : "outlook"
}

/** The mailboxes this Lace has connected, in the order it picks them. */
export function connectedMailboxes(apps: LaceAppDto[]): LaceAppDto[] {
  return MAILBOXES.flatMap((mailbox) => apps.filter((a) => a.platform === mailbox && a.status !== null))
}

export function onAccount(outreach: LaceOutreachDto[], account: AccountKey, apps: LaceAppDto[]): LaceOutreachDto[] {
  if (account === "all") return outreach.filter((m) => OUTREACH_CHANNELS.has(m.channel))
  if (account === "linkedin") return outreach.filter((m) => m.channel === "linkedin")
  return outreach.filter((m) => m.channel === "email" && mailboxOf(m, apps) === account)
}

/** The accounts to switch between: each connected mailbox, LinkedIn if
 * connected, then any that has messages but isn't connected. `apps` is the
 * Lace's (its own accounts or the shared ones); LinkedIn is the founder's. */
export function messagingAccounts(apps: LaceAppDto[], connections: ConnectionDto[],
                                  outreach: LaceOutreachDto[]): MessagingAccount[] {
  const waiting = (key: MessagingAccount["key"]) => onAccount(outreach, key, apps).filter(waitsOnFounder).length
  const accounts: MessagingAccount[] = connectedMailboxes(apps).map((app) => ({
    key: app.platform as Mailbox, platform: app.platform as Platform, label: app.label, detail: app.account_name,
    state: app.connected ? "connected" : "attention", waiting: waiting(app.platform as Mailbox), sends: app.sends_email,
  }))
  const linkedin = connections.find((c) => c.platform === "linkedin")
  if (linkedin) {
    accounts.push({ key: "linkedin", platform: "linkedin", label: PLATFORM_LABEL.linkedin, detail: linkedin.display_name,
                    state: linkedin.status === "live" ? "connected" : "attention", waiting: waiting("linkedin"),
                    sends: false })
  }
  const keys = new Set(outreach.filter((m) => OUTREACH_CHANNELS.has(m.channel))
    .map((m): MessagingAccount["key"] => (m.channel === "email" ? mailboxOf(m, apps) : "linkedin")))
  for (const key of keys) {
    if (accounts.some((a) => a.key === key)) continue
    accounts.push({ key, platform: key, label: PLATFORM_LABEL[key], detail: null, state: "none", waiting: waiting(key),
                    sends: false })
  }
  return accounts
}
