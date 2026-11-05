import type { ConnectionDto, LaceOutreachDto, OutreachChannel } from "@/lib/api"
import { PLATFORM_LABEL, type Platform } from "@/lib/platforms"

import { OUTREACH_CHANNELS, waitsOnFounder } from "./outreach-threads"

/** Which account Messaging shows: every one, or one channel's. A user has at
 * most one connection per platform, so a channel names an account. */
export type AccountKey = "all" | OutreachChannel

export const CHANNEL_PLATFORM: Record<OutreachChannel, Platform> = {
  email: "gmail", linkedin: "linkedin", x: "x", instagram: "instagram", facebook: "facebook", tiktok: "tiktok",
  telegram: "telegram",
}

/** Platforms Outreach offers to connect, in order: mailboxes, and LinkedIn for notes the founder sends. */
export const MESSAGING_PLATFORMS: Platform[] = ["gmail", "outlook", "linkedin"]

/** The mailboxes a Lace sends email from, in the order it picks them (backend outreach.EMAIL_APPS). */
const MAILBOXES: Platform[] = ["gmail", "outlook"]

export interface MessagingAccount {
  key: OutreachChannel
  platform: Platform
  label: string
  /** Who the account is (an address or @handle), when known. */
  detail: string | null
  /** connected: live; attention: connected but needs signing in again; none:
   * outreach exists on this channel without a connection (LinkedIn drafts). */
  state: "connected" | "attention" | "none"
  /** Drafts and unread replies on it. */
  waiting: number
}

/** The mailbox email goes from: the first live one, else the first connected. */
function mailbox(connections: ConnectionDto[]): ConnectionDto | undefined {
  const mail = MAILBOXES.flatMap((platform) => connections.filter((c) => c.platform === platform))
  return mail.find((c) => c.status === "live") ?? mail[0]
}

/** With both Gmail and Outlook connected, which one email goes from, and how
 * to use the other; null with one mailbox or none. */
export function mailboxNote(connections: ConnectionDto[], name: string): string | null {
  const mail = mailbox(connections)
  const other = connections.find((c) => MAILBOXES.includes(c.platform as Platform) && c.platform !== mail?.platform)
  if (!mail || !other) return null
  const sends = PLATFORM_LABEL[mail.platform as Platform]
  return `${name} sends email from ${sends}${mail.display_name ? ` (${mail.display_name})` : ""}. `
    + `${PLATFORM_LABEL[other.platform as Platform]} is connected too: to send from it, switch ${sends} off for ${name} `
    + "in its settings, under Apps & accounts."
}

/** The accounts to switch between: the mailbox email goes from, LinkedIn if
 * connected, then any channel that has messages but no connection. */
export function messagingAccounts(connections: ConnectionDto[], outreach: LaceOutreachDto[]): MessagingAccount[] {
  const waiting = (channel: OutreachChannel) => outreach.filter((m) => m.channel === channel && waitsOnFounder(m)).length
  const connected = (key: OutreachChannel, connection: ConnectionDto): MessagingAccount => ({
    key, platform: connection.platform as Platform, label: PLATFORM_LABEL[connection.platform as Platform],
    detail: connection.display_name, state: connection.status === "live" ? "connected" : "attention",
    waiting: waiting(key),
  })
  const accounts: MessagingAccount[] = []
  const mail = mailbox(connections)
  if (mail) accounts.push(connected("email", mail))
  const linkedin = connections.find((c) => c.platform === "linkedin")
  if (linkedin) accounts.push(connected("linkedin", linkedin))
  for (const channel of new Set(outreach.map((m) => m.channel))) {
    if (!OUTREACH_CHANNELS.has(channel) || accounts.some((a) => a.key === channel)) continue
    accounts.push({ key: channel, platform: CHANNEL_PLATFORM[channel], label: PLATFORM_LABEL[CHANNEL_PLATFORM[channel]],
                    detail: null, state: "none", waiting: waiting(channel) })
  }
  return accounts
}

export function onAccount(outreach: LaceOutreachDto[], account: AccountKey): LaceOutreachDto[] {
  return account === "all" ? outreach.filter((m) => OUTREACH_CHANNELS.has(m.channel))
    : outreach.filter((m) => m.channel === account)
}
