import type { CompetitorLeadDto, IcpDto, OfferSnapshot } from '@/lib/api'

import type { BuyerType } from '@/lib/buyer-type'

export type { BuyerType } from '@/lib/buyer-type'
export { BUYER_TYPES } from '@/lib/buyer-type'

export type ProductCategory =
  | 'saas'
  | 'paas'
  | 'iaas'
  | 'marketplace'
  | 'hardware'
  | 'service'
  | 'agency'
  | 'consulting'
  | 'other'

export type MarketFitVerdict = 'strong' | 'moderate' | 'weak' | 'unclear'

export type PricingSource = 'site' | 'market_suggestion'

export interface SnapshotFeature {
  name: string | null
  description: string | null
  differentiator: string | null
}

export interface Pricing {
  tier: string
  monthly_sub: string | null
  yearly_sub: string | null
  features: string[]
}

export interface MarketExtraction {
  buyer_type: BuyerType | null
  category: ProductCategory | null
  target_audience: string | null
  pricing: Pricing[]
  pricing_source: PricingSource | null
  target_geo: string[]
  market_fit: MarketFitVerdict | null
  market_fit_reasoning: string | null
}

/** The ICP exactly as the API returns it (B2C fields included). */
export type ICP = IcpDto
export type CompetitorLead = CompetitorLeadDto

export interface ProductState {
  product_snapshot: OfferSnapshot | null
  product_domain_understanding: string | null
  product_market_fit_understanding: string | null
  market_data: MarketExtraction | null
  icp: ICP | null
}


export const PRODUCT_CATEGORIES: ProductCategory[] = [
  'saas',
  'paas',
  'iaas',
  'marketplace',
  'hardware',
  'service',
  'agency',
  'consulting',
  'other',
]

export const FIT_VERDICTS: MarketFitVerdict[] = [
  'strong',
  'moderate',
  'weak',
  'unclear',
]