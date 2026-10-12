import { useEffect } from 'react'

import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { BUYER_EXPLAINER, BUYER_LABEL, useBuyerType } from '@/lib/buyer-type'
import { ensureInsightsLoaded } from '@/lib/insights-store'

/** Who the offer sells to, once the market research has decided it, with
 * what that changes about targets and outreach. Nothing shows before then. */
export function BuyerBadge({ workspaceId }: { workspaceId: string | undefined }) {
  useEffect(() => ensureInsightsLoaded(workspaceId), [workspaceId])
  const buyer = useBuyerType(workspaceId)
  if (!buyer) return null

  return (
    <Tooltip>
      <TooltipTrigger render={<Badge variant="outline" className="cursor-default border-amber-500/40 text-amber-500" />}>
        {BUYER_LABEL[buyer]}
      </TooltipTrigger>
      <TooltipContent side="bottom">{BUYER_EXPLAINER[buyer]}</TooltipContent>
    </Tooltip>
  )
}
