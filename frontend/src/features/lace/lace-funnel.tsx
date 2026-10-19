import { useEffect, useState } from "react"
import { ChevronRight } from "lucide-react"

import { getLaceFunnel, type FunnelDto } from "@/lib/api"

const STEPS: { key: keyof FunnelDto; label: string }[] = [
  { key: "accounts", label: "Target accounts" },
  { key: "contacted", label: "Contacted" },
  { key: "replied", label: "Replied" },
  { key: "interested", label: "Interested" },
]

/** How far the Lace's target accounts have come, in one line. Refetched
 * whenever `refreshKey` changes (new activity, a message sent). Shows
 * nothing until it loads, or if it cannot. */
export function LaceFunnel({ laceId, refreshKey }: { laceId: string; refreshKey: string }) {
  const [funnel, setFunnel] = useState<FunnelDto | null>(null)

  useEffect(() => {
    let cancelled = false
    getLaceFunnel(laceId)
      .then((next) => !cancelled && setFunnel(next))
      .catch(() => undefined) // a missing funnel line is not worth an error on the Feed
    return () => { cancelled = true }
  }, [laceId, refreshKey])

  if (!funnel) return null
  return (
    <ol aria-label="Pipeline" className="flex flex-wrap items-center gap-x-1 gap-y-2 rounded-xl border bg-card px-4 py-3">
      {STEPS.map((step, i) => (
        <li key={step.key} className="flex items-center gap-1">
          {i > 0 && <ChevronRight aria-hidden className="size-4 text-muted-foreground" />}
          <span className="text-lg font-medium tabular-nums">{funnel[step.key]}</span>
          <span className="text-sm text-muted-foreground">{step.label}</span>
        </li>
      ))}
    </ol>
  )
}
