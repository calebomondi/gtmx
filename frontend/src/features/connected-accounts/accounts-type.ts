// Connection model for the /accounts channel board, backed by the server's
// Composio-held connections (/api/v1/connections).

import { deleteConnection, listConnections, startConnection, type ConnectionDto } from '@/lib/api'

export type Platform = 'gmail' | 'linkedin' | 'instagram' | 'tiktok' | 'x'

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
  linkedin: 'LinkedIn',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  x: 'X',
}

/** Empty string means "no icon asset" — the tile renders a letter badge. */
export const PLATFORM_ICON: Record<Platform, string> = {
  gmail: '/gmail.svg',
  linkedin: '/linkedin.svg',
  instagram: '/instagram.svg',
  tiktok: '/tiktok.svg',
  x: '',
}

/** Every channel the app can connect, in display order. */
export const ALL_PLATFORMS: Platform[] = ['gmail', 'linkedin', 'instagram', 'tiktok', 'x']

/** What outreach does through each channel. Sending always needs the user's
 *  explicit click; the agent drafts, it never sends on its own. */
const CAPABILITIES: Record<Platform, Connection['capabilities']> = {
  gmail: [
    { label: 'Send emails you approve', allowed: true },
    { label: 'Read replies to those emails', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
  linkedin: [
    { label: 'Post updates you approve', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
  instagram: [
    { label: 'Publish posts you approve', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
  tiktok: [
    { label: 'Publish content you approve', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
  x: [
    { label: 'Post and reply as you approve', allowed: true },
    { label: 'Send without your approval', allowed: false },
  ],
}

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
