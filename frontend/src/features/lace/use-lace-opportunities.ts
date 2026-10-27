import { useCallback, useEffect, useState } from "react"

import { listLaceOpportunities, setLaceOpportunityStatus, type Dismissal, type LaceOpportunityDto } from "@/lib/api"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export interface LaceOpportunities {
  /** Saved and still open. */
  opportunities: LaceOpportunityDto[]
  /** Found by a search, waiting for the founder. */
  suggested: LaceOpportunityDto[]
  loading: boolean
  error: string | null
  save: (id: string) => Promise<void>
  /** With `why`, later searches steer clear of the like. */
  dismiss: (id: string, why?: Dismissal) => Promise<void>
}

/** A Lace's open opportunities and the ones waiting to be saved. Refetched
 * when `refreshKey` changes (a search finished). */
export function useLaceOpportunities(laceId: string, refreshKey = ""): LaceOpportunities {
  const [opportunities, setOpportunities] = useState<LaceOpportunityDto[]>([])
  const [suggested, setSuggested] = useState<LaceOpportunityDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([listLaceOpportunities(laceId, "open"), listLaceOpportunities(laceId, "suggested")])
      .then(([saved, waiting]) => {
        if (cancelled) return
        setOpportunities(saved)
        setSuggested(waiting)
      })
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [laceId, refreshKey])

  const save = useCallback(async (id: string) => {
    try {
      const saved = await setLaceOpportunityStatus(laceId, id, "open")
      setSuggested((prev) => prev.filter((o) => o.id !== id))
      setOpportunities((prev) => [...prev, saved])
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const dismiss = useCallback(async (id: string, why?: Dismissal) => {
    try {
      await setLaceOpportunityStatus(laceId, id, "dismissed", why)
      setOpportunities((prev) => prev.filter((o) => o.id !== id))
      setSuggested((prev) => prev.filter((o) => o.id !== id))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  return { opportunities, suggested, loading, error, save, dismiss }
}
