import { useCallback, useEffect, useState } from "react"

import { dismissLaceOpportunity, listLaceOpportunities, type LaceOpportunityDto } from "@/lib/api"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** A Lace's open opportunities, loaded when shown. */
export function useLaceOpportunities(laceId: string) {
  const [opportunities, setOpportunities] = useState<LaceOpportunityDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listLaceOpportunities(laceId)
      .then((rows) => !cancelled && setOpportunities(rows))
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [laceId])

  const dismiss = useCallback(async (id: string) => {
    try {
      await dismissLaceOpportunity(laceId, id)
      setOpportunities((prev) => prev.filter((o) => o.id !== id))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  return { opportunities, loading, error, dismiss }
}
