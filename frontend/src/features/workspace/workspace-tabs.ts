import { Bot, Newspaper, Package, Send, Swords, type LucideIcon } from 'lucide-react'

import type { WorkspaceTab } from '@/lib/workspace-tab'

/** The workspace's sections in navigation order, with their labels and icons. */
export const WORKSPACE_TABS: { value: WorkspaceTab; name: string; icon: LucideIcon }[] = [
  { value: 'feed', name: 'Feed', icon: Newspaper },
  { value: 'outreach', name: 'Reach Out', icon: Send },
  { value: 'product', name: 'Offer', icon: Package },
  { value: 'competition', name: 'Competitors', icon: Swords },
  { value: 'agent', name: 'Agent', icon: Bot },
]
