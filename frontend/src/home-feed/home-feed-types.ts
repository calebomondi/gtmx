import type { Signal, SignalCategory } from '@/feed/feed-types'

export interface WorkspaceRef {
  id: string
  name: string
}

export type HomeSignal = Signal & {
  workspace: WorkspaceRef
}

export type HomeCategory = Exclude<SignalCategory, 'market'>

export type HomeCategoryFilter = 'all' | HomeCategory

export type WorkspaceTab = 'feed' | 'outreach' | 'product' | 'competition' | 'agent'

export const CATEGORY_TARGET_TAB: Record<HomeCategory, WorkspaceTab> = {
  inbound: 'feed',
  outbound: 'feed',
  opportunity: 'feed',
  competitor: 'competition',
  product: 'product',
  agent: 'agent',
}
