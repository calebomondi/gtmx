import type { ConnectionDto, LaceOutreachDto, OutreachChannel } from "@/lib/api"
import { PLATFORM_LABEL, type Platform } from "@/lib/platforms"

import { waitsOnFounder } from "./outreach-threads"

/** Which account Messaging shows: every one, or one channel's. A user has at
 * most one connection per platform, so a channel names an account. */
export type AccountKey = "all" | OutreachChannel

export const CHANNEL_PLATFORM: Record<OutreachChannel, Platform> = {
  email: "gmail", linkedin: "linkedin", x: "x", instagram: "instagram", facebook: "facebook", tiktok: "tiktok",
  telegram: "telegram",
}

/** Platforms Outreach offers to connect, in order: email, and LinkedIn for notes the founder sends. */
export const MESSAGING_PLATFORMS: Platform[] = ["gmail", "linkedin"]

/** The channels Outreach shows; social ones live in Social. */
export const OUTREACH_CHANNELS: ReadonlySet<OutreachChannel> = new Set(["email", "linkedin"])

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

function channelOf(platform: string): OutreachChannel | null {
  const found = (Object.entries(CHANNEL_PLATFORM) as [OutreachChannel, Platform][]).find(([, p]) => p === platform)
  return found ? found[0] : null
}

/** The accounts to switch between: every connected outreach account, then
 * any channel that has messages but no connection. */
export function messagingAccounts(connections: ConnectionDto[], outreach: LaceOutreachDto[]): MessagingAccount[] {
  const waiting = (channel: OutreachChannel) => outreach.filter((m) => m.channel === channel && waitsOnFounder(m)).length
  const accounts: MessagingAccount[] = []
  for (const connection of connections) {
    const channel = channelOf(connection.platform)
    if (!channel || !OUTREACH_CHANNELS.has(channel) || accounts.some((a) => a.key === channel)) continue
    accounts.push({
      key: channel, platform: CHANNEL_PLATFORM[channel], label: PLATFORM_LABEL[CHANNEL_PLATFORM[channel]],
      detail: connection.display_name, state: connection.status === "live" ? "connected" : "attention",
      waiting: waiting(channel),
    })
  }
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
