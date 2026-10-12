import type { OfferSnapshot } from '@/lib/api'

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

export interface CompetitorLead {
  competitor_name: string
  search_queries: string[]
  pain_angles: string[]
}

export interface ICP {
  product_name: string | null
  buyer_type: string | null
  industries: string[]
  company_sizes: string[]
  geo: string[]
  buyer_titles: string[]
  exclusions: string[]
  pain_signals: string[]
  intent_keywords: string[]
  competitor_leads: CompetitorLead[]
}

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