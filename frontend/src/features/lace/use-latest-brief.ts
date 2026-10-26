import { useEffect, useState } from "react"

import { getLatestLaceBrief, type LaceBriefDto } from "@/lib/api"

// While the Lace writes its brief, look again this often.
const WRITING_POLL_MS = 8_000

export interface LatestBrief {
  brief: LaceBriefDto | null
  loading: boolean
  error: string | null
}

/** A Lace's latest brief. Fetched again when `refreshKey` changes (new
 * activity came in), and every few seconds while it is being written. */
export function useLatestBrief(laceId: string, refreshKey: string): LatestBrief {
  const [brief, setBrief] = useState<LaceBriefDto | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const writing = brief?.state === "writing"

  useEffect(() => {
    let cancelled = false
    const load = () => getLatestLaceBrief(laceId)
      .then((next) => {
        if (cancelled) return
        setBrief(next)
        setError(null)
      })
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false))
    void load()
    const timer = writing ? setInterval(load, WRITING_POLL_MS) : undefined
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [laceId, refreshKey, writing])

  return { brief, loading, error }
}
