// Connection model for the /accounts channel board.
//
// v1 hydrates from `mockConnections` behind the `fetchConnections()` seam so
// swapping in the real backend (OAuth + connection table) is a one-function
// change.

export type Platform = 'gmail' | 'linkedin' | 'instagram' | 'tiktok' | 'facebook' | 'x'

export type ConnectionStatus = 'live' | 'needs_attention'

export interface Connection {
  id: string
  platform: Platform
  /** Email, @handle, or display name — the tile's grounding label. */
  username: string
  /** Display name under the handle when it differs (e.g. LinkedIn profile). */
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
  facebook: 'Facebook',
  x: 'X',
}

/** Empty string means "no icon asset" — the tile renders a letter badge. */
export const PLATFORM_ICON: Record<Platform, string> = {
  gmail: '/gmail.svg',
  linkedin: '/linkedin.svg',
  instagram: '/instagram.svg',
  tiktok: '/tiktok.svg',
  facebook: '/facebook.svg',
  x: '',
}

/** Every platform the app can connect — the grid shows one tile per
 *  connection plus one "available" tile for platforms with none. */
export const ALL_PLATFORMS: Platform[] = [
  'gmail',
  'linkedin',
  'instagram',
  'tiktok',
  'facebook',
  'x',
]

const MOCK: Connection[] = [
  {
    id: 'conn_gmail_jane',
    platform: 'gmail',
    username: 'jane@acme.com',
    status: 'live',
    connectedAt: '2026-03-04T10:12:00Z',
    lastSync: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    capabilities: [
      { label: 'Send email from this inbox', allowed: true },
      { label: 'Read replies & threads', allowed: true },
      { label: 'Read contacts', allowed: false },
    ],
    usageCount: 12,
  },
  {
    id: 'conn_gmail_work',
    platform: 'gmail',
    username: 'jane@work.com',
    status: 'live',
    connectedAt: '2026-07-19T09:05:00Z',
    lastSync: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    capabilities: [
      { label: 'Send email from this inbox', allowed: true },
      { label: 'Read replies & threads', allowed: true },
      { label: 'Read contacts', allowed: false },
    ],
    usageCount: 4,
  },
  {
    id: 'conn_linkedin_jane',
    platform: 'linkedin',
    username: 'jane-doe',
    displayName: 'Jane Doe · VP Growth',
    status: 'live',
    connectedAt: '2026-03-04T10:15:00Z',
    lastSync: new Date(Date.now() - 11 * 60 * 1000).toISOString(),
    capabilities: [
      { label: 'Send connection requests', allowed: true },
      { label: 'Send InMails & messages', allowed: true },
      { label: 'Post on your behalf', allowed: false },
    ],
    usageCount: 8,
  },
  {
    id: 'conn_tiktok_janedoe',
    platform: 'tiktok',
    username: '@janedoe',
    status: 'live',
    connectedAt: '2026-04-21T08:40:00Z',
    lastSync: new Date(Date.now() - 47 * 60 * 1000).toISOString(),
    capabilities: [
      { label: 'Read profile & bio', allowed: true },
      { label: 'Send direct messages', allowed: true },
      { label: 'Comment on posts', allowed: false },
    ],
    usageCount: 3,
  },
  {
    id: 'conn_facebook_jane',
    platform: 'facebook',
    username: 'Jane Doe',
    status: 'needs_attention',
    connectedAt: '2026-01-15T14:02:00Z',
    lastSync: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    capabilities: [
      { label: 'Read page messages', allowed: true },
      { label: 'Reply to messages', allowed: true },
      { label: 'Post on your behalf', allowed: false },
    ],
    usageCount: 1,
  },
]

/**
 * Seam for the real backend. Today: mocks with a hair of latency so loading
 * states are exercised. Later: replace the body with an API call.
 */
export async function fetchConnections(): Promise<Connection[]> {
  await new Promise((resolve) => setTimeout(resolve, 250))
  return MOCK.map((c) => ({ ...c }))
}

/** Agent-scoped identities — the workspace's agent has its own accounts. */
export const AGENT_IDENTITY: Record<Platform, string> = {
  gmail: 'agent@gtmx-team.com',
  linkedin: 'GTM Agent',
  instagram: '@gtmx.agent',
  tiktok: '@gtmx.agent',
  facebook: 'GTM Agent',
  x: '@gtmx_agent',
}

/**
 * Stub for starting an agent-level OAuth connection on a platform.
 * Replace with the real connect endpoint later.
 */
export async function connectAgentConnection(platform: Platform): Promise<Connection> {
  await new Promise((resolve) => setTimeout(resolve, 900))
  return {
    id: `agent_${platform}`,
    platform,
    username: AGENT_IDENTITY[platform],
    status: 'live',
    connectedAt: new Date().toISOString(),
    lastSync: new Date().toISOString(),
    capabilities: [],
    usageCount: 0,
  }
}
