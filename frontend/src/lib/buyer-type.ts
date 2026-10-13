import { useInsights } from '@/lib/insights-store'

export type BuyerType = 'b2b' | 'b2c' | 'both'

export const BUYER_TYPES: BuyerType[] = ['b2b', 'b2c', 'both']

export const BUYER_LABEL: Record<BuyerType, string> = {
  b2b: 'B2B',
  b2c: 'B2C',
  both: 'B2B + B2C',
}

/** What the buyer type changes downstream, in the user's terms. */
export const BUYER_EXPLAINER: Record<BuyerType, string> = {
  b2b: 'Sold to organisations. Targets are companies, and outreach is a sales pitch to the people who buy.',
  b2c: 'Sold to individuals. Targets are the communities, creators and events your buyers follow, pitched as partnerships.',
  both: 'Sold to organisations and individuals. Targets are companies to sell to, plus communities, creators and events to partner with.',
}

export function asBuyerType(value: string | null | undefined): BuyerType | null {
  const lowered = value?.trim().toLowerCase()
  return BUYER_TYPES.find((t) => t === lowered) ?? null
}

/** The workspace's buyer type: the market stage decides it, the ICP repeats it. */
export function useBuyerType(workspaceId: string | undefined): BuyerType | null {
  const { insights } = useInsights(workspaceId)
  return asBuyerType(insights?.market_data?.buyer_type ?? insights?.icp?.buyer_type)
}

/** Communities, creators, events and platforms are reached as partners, not sold to. */
export function isVenue(accountType: string): boolean {
  return accountType.toLowerCase() !== 'company'
}

export const PITCH = {
  sales: {
    label: 'Sales pitch',
    hint: 'This account could buy, so your GTM specialist writes to the person who decides.',
  },
  partnership: {
    label: 'Partnership pitch',
    hint: "This account reaches your buyers, so your GTM specialist proposes a collaboration for its audience, not a sale.",
  },
} as const

export function pitchFor(accountType: string) {
  return isVenue(accountType) ? PITCH.partnership : PITCH.sales
}


/** The three ways a consumer offer reaches people, each with its own pitch. */
export type VenueGroup = 'community' | 'creator' | 'event'

export const VENUE_GROUPS: VenueGroup[] = ['community', 'creator', 'event']

export const VENUE_GROUP_LABEL: Record<VenueGroup, string> = {
  community: 'Communities',
  creator: 'Creators & influencers',
  event: 'Events',
}

const ACCOUNT_GROUP: Record<string, VenueGroup> = {
  community: 'community', platform: 'community', creator: 'creator', event: 'event',
}

const CHANNEL_GROUP: Record<string, VenueGroup> = {
  community: 'community', forum: 'community', marketplace: 'community', social_platform: 'community',
  creator: 'creator', newsletter: 'creator', event: 'event',
}

/** A found target's group; null for a company. */
export function venueGroupOfAccount(accountType: string): VenueGroup | null {
  return ACCOUNT_GROUP[accountType.toLowerCase()] ?? null
}

/** An ICP channel's group, from the kind of venue it is. */
export function venueGroupOfChannel(channelType: string): VenueGroup | null {
  return CHANNEL_GROUP[channelType.toLowerCase()] ?? null
}

