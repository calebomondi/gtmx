import { useEffect, useState } from 'react'

import { listRunSteps, type RunStepDto } from '@/lib/api'

// Steps arrive every few seconds; polling faster than this only adds requests.
const POLL_MS = 2000

/** The progress steps of a running agent run, polled while `live`. Fetches
 * only steps after the last one seen, and keeps what it has across errors. */
export function useRunSteps(runId: string | null, live: boolean): RunStepDto[] {
  const [steps, setSteps] = useState<{ runId: string | null; items: RunStepDto[] }>({ runId: null, items: [] })
  const items = steps.runId === runId ? steps.items : []

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    let after = 0

    const poll = async () => {
      try {
        const fresh = await listRunSteps(runId, after)
        if (cancelled || fresh.length === 0) return
        after = fresh[fresh.length - 1].id
        setSteps((prev) => ({ runId, items: [...(prev.runId === runId ? prev.items : []), ...fresh] }))
      } catch {
        // A missed poll is retried on the next tick; the run itself is unaffected.
      }
    }

    void poll()
    const timer = live ? window.setInterval(() => void poll(), POLL_MS) : undefined
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearInterval(timer)
    }
  }, [runId, live])

  return items
}
