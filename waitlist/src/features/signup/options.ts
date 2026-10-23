import type { SellsTo, Stage } from '../../lib/api'

export const STAGES: { value: Stage; label: string }[] = [
  { value: 'idea', label: 'Idea' },
  { value: 'pre_revenue', label: 'Building, no revenue yet' },
  { value: 'revenue', label: 'Earning revenue' },
  { value: 'scaling', label: 'Scaling' },
]

export const SELLS_TO: { value: SellsTo; label: string }[] = [
  { value: 'b2b', label: 'Businesses' },
  { value: 'b2c', label: 'Consumers' },
  { value: 'both', label: 'Both' },
]
