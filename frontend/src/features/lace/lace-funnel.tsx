import { useEffect, useState } from "react"

import { Skeleton } from "@/components/ui/skeleton"
import { getLaceFunnel, type FunnelDto } from "@/lib/api"

const STEPS: { key: keyof FunnelDto; label: string }[] = [
  { key: "accounts", label: "Target accounts" },
  { key: "contacted", label: "Contacted" },
  { key: "replied", label: "Replied" },
  { key: "interested", label: "Interested" },
]

function share(part: number, whole: number): string | null {
  return whole > 0 ? `${Math.round((part / whole) * 100)}%` : null
}

/** How far the Lace's target accounts have come: one tile per stage, each
 * with its share of the stage before. Refetched whenever `refreshKey`
 * changes (new activity, a message sent). */
export function LaceFunnel({ laceId, refreshKey }: { laceId: string; refreshKey: string }) {
  const [funnel, setFunnel] = useState<FunnelDto | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    getLaceFunnel(laceId)
      .then((next) => !cancelled && setFunnel(next))
      .catch(() => !cancelled && setFailed(true)) // the Feed works without it
    return () => { cancelled = true }
  }, [laceId, refreshKey])

  if (failed) return null
  if (!funnel) return <Skeleton className="h-[4.5rem] w-full rounded-xl" />
  const top = Math.max(funnel.accounts, 1)
  return (
    <ol aria-label="Pipeline" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {STEPS.map((step, i) => {
        const value = funnel[step.key]
        const ofPrevious = i > 0 ? share(value, funnel[STEPS[i - 1].key]) : null
        return (
          <li key={step.key} className="flex flex-col gap-1.5 rounded-xl border bg-background/60 px-3 py-2.5">
            <span className="flex items-baseline justify-between gap-2">
              <span className="text-xl font-semibold tabular-nums">{value}</span>
              {ofPrevious && <span className="text-[11px] text-muted-foreground tabular-nums">{ofPrevious}</span>}
            </span>
            <span className="text-xs text-muted-foreground">{step.label}</span>
            {/* The bar's length is data, so it is the one inline style. */}
            <span aria-hidden className="h-1 overflow-hidden rounded-full bg-muted">
              <span className="block h-full rounded-full bg-theme transition-[width] duration-500"
                    style={{ width: `${Math.min(100, (value / top) * 100)}%` }} />
            </span>
          </li>
        )
      })}
    </ol>
  )
}
