// Connection model for the /accounts channel board, backed by the server's
// Composio-held connections (/api/v1/connections).

import { deleteConnection, listConnections, startConnection, type ConnectionDto } from '@/lib/api'

export type Platform = 'gmail' | 'googlecalendar' | 'linkedin' | 'instagram' | 'facebook' | 'tiktok' | 'x'

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

export const PLATFORM_LABEL: Record<Platform, string> = {
  gmail: 'Gmail',
  googlecalendar: 'Google Calendar',
  linkedin: 'LinkedIn',
  instagram: 'Instagram',
  facebook: 'Facebook',
  tiktok: 'TikTok',
  x: 'X',
}

/** Empty string means "no icon asset" — the tile renders a glyph instead. */
export const PLATFORM_ICON: Record<Platform, string> = {
  gmail: '/gmail.svg',
  googlecalendar: '',
  linkedin: '/linkedin.svg',
  instagram: '/instagram.svg',
  facebook: '/facebook.svg',
  tiktok: '/tiktok.svg',
  x: '',
}

/** Every channel the app can connect, in display order. */
export const ALL_PLATFORMS: Platform[] = ['gmail', 'googlecalendar', 'linkedin', 'instagram', 'facebook', 'tiktok', 'x']

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
    { label: 'Publish content you approve', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
  x: [
    { label: 'Send DMs you approve', allowed: true },
    { label: 'Send without your approval', allowed: false },
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

/** Sends the browser to the platform's sign-in (via Composio). */
export async function beginConnection(platform: Platform): Promise<void> {
  const { redirect_url } = await startConnection(platform)
  window.location.assign(redirect_url)
}

export async function disconnectConnection(connectionId: string): Promise<void> {
  await deleteConnection(connectionId)
}
