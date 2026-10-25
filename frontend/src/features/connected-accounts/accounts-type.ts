// Connection model for the /accounts channel board, backed by the server's
// Composio-held connections (/api/v1/connections).

import { deleteConnection, listConnections, type ConnectionDto } from '@/lib/api'
import { PLATFORM_LABEL, type Platform } from '@/lib/platforms'

export type ConnectionStatus = 'live' | 'pending' | 'needs_attention'

export interface Connection {
  id: string
  platform: Platform
  /** Provider display name (email, @handle, name) or the platform label. */
  username: string
  displayName?: string
  status: ConnectionStatus
  connectedAt: string // ISO date
  lastSync: string // ISO date
  /** What the agent can do through this connection. */
  capabilities: Array<{ label: string; allowed: boolean }>
  /** Outreach runs that used this channel. */
  usageCount: number
}

/** What the agents do through each channel, as each provider allows it.
 *  Sending always needs the user's explicit click; agents draft, never send. */
/** Platforms that only let a business answer people who wrote first. Said
 *  up front, before connecting, so nobody expects cold DMs there. */
export const REPLY_ONLY_NOTE: Partial<Record<string, string>> = {
  instagram:
    "Instagram doesn't let businesses start conversations. Engage with their posts; once someone messages you, your team picks up the conversation and drafts every reply for you to send.",
  facebook:
    "Facebook doesn't let Pages start conversations. Once someone messages your Page, your team picks up the conversation and drafts every reply for you to send.",
}

const CAPABILITIES: Record<Platform, Connection['capabilities']> = {
  gmail: [
    { label: 'Send emails you approve', allowed: true },
    { label: 'Read replies to those emails', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
  googlecalendar: [
    { label: 'Find free slots for meetings', allowed: true },
    { label: 'Add meetings you approve', allowed: true },
    { label: 'Change your calendar without approval', allowed: false },
  ],
  linkedin: [
    { label: 'Show who you are on drafts', allowed: true },
    { label: 'Send messages (LinkedIn offers no messaging API: you paste drafts yourself)', allowed: false },
  ],
  instagram: [
    { label: 'Read and answer DMs from people who wrote to you', allowed: true },
    { label: 'Cold DMs (Instagram only allows replies within 24 hours)', allowed: false },
  ],
  facebook: [
    { label: "Read and answer your Page's messages", allowed: true },
    { label: 'Cold messages (Facebook only allows replies within 24 hours)', allowed: false },
  ],
  tiktok: [
    { label: 'Read your public videos, how they did and their comments (from your handle, no connection needed)', allowed: true },
    { label: 'Reply or post for you (TikTok\'s API allows neither)', allowed: false },
  ],
  telegram: [
    { label: 'Read messages to your bot (and group mentions), with answers you send', allowed: true },
    { label: 'Send your brief to a chat or group you choose', allowed: true },
    { label: 'Post to your channel when you approve', allowed: true },
    { label: 'Start chats with people (Telegram bots can only answer)', allowed: false },
  ],
  x: [
    { label: 'Read your public posts and how they did (from your handle, no connection needed)', allowed: true },
    { label: 'Send DMs you approve', allowed: true },
    { label: 'Post, reply, like and repost when you approve', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
  // The apps below connect now; their skills arrive one by one (COMING_SOON).
  outlook: [
    { label: 'Send emails you approve, and read their replies', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
  whatsapp: [
    { label: 'Start chats with your approved templates, when you approve', allowed: true },
    { label: 'Answer replies you approve', allowed: true },
    { label: 'Message without your approval', allowed: false },
  ],
  zoho: [
    { label: 'Summarise your pipeline: deals by stage, totals, stale deals', allowed: true },
    { label: 'Check whether someone is already a lead', allowed: true },
    { label: 'Add leads when you approve', allowed: true },
    { label: 'Change your CRM without approval', allowed: false },
  ],
  hubspot: [
    { label: 'Summarise your pipeline: deals by stage, totals, stale deals', allowed: true },
    { label: 'Check whether a company or person is already in HubSpot', allowed: true },
    { label: 'Add leads when you approve', allowed: true },
    { label: 'Change your CRM without approval', allowed: false },
  ],
  googlesheets: [
    { label: 'Read and summarise a sheet, or import a lead list', allowed: true },
    { label: 'Export accounts and contacts when you approve', allowed: true },
    { label: 'Change your sheets without approval', allowed: false },
  ],
  notion: [
    { label: 'Search your workspace for context', allowed: true },
    { label: 'Write the brief or a report as a page when you approve', allowed: true },
    { label: 'Change your pages without approval', allowed: false },
  ],
  slack: [
    { label: "Search your team's messages for context", allowed: true },
    { label: 'Post messages you approve to a channel you choose', allowed: true },
    { label: 'Message people without approval', allowed: false },
  ],
  asana: [
    { label: 'Create follow-up tasks when you approve', allowed: true },
    { label: 'Summarise open and overdue tasks', allowed: true },
    { label: 'Change tasks without approval', allowed: false },
  ],
  calendly: [
    { label: 'Put your booking links in drafts', allowed: true },
    { label: 'See booked meetings, and who booked', allowed: true },
    { label: 'Cancel or move meetings', allowed: false },
  ],
}

export const capabilitiesFor = (platform: Platform): Connection['capabilities'] => CAPABILITIES[platform]

function toConnection(dto: ConnectionDto): Connection {
  const platform = dto.platform as Platform
  return {
    id: dto.id,
    platform,
    username: dto.display_name ?? PLATFORM_LABEL[platform],
    status: dto.status,
    connectedAt: dto.created_at ?? new Date().toISOString(),
    lastSync: dto.updated_at ?? dto.created_at ?? new Date().toISOString(),
    capabilities: CAPABILITIES[platform],
    usageCount: 0,
  }
}

export interface ConnectionState {
  connections: Connection[]
  /** Channels the user can connect now (others need app-level OAuth setup). */
  available: Set<Platform>
}

export async function fetchConnectionState(): Promise<ConnectionState> {
  const { channels, connections } = await listConnections()
  return {
    connections: connections.filter((c) => c.platform in PLATFORM_LABEL).map(toConnection),
    available: new Set(channels.filter((c) => c.available).map((c) => c.platform as Platform)),
  }
}

export async function fetchConnections(): Promise<Connection[]> {
  return (await fetchConnectionState()).connections
}

export async function disconnectConnection(connectionId: string): Promise<void> {
  await deleteConnection(connectionId)
}
