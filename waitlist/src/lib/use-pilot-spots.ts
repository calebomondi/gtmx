import { useCallback, useEffect, useState } from 'react'

import { getPilotSpots, type PilotSpots } from './api'

// How often an open page checks the count, so spots taken by others show as
// they go. Only while the page is in view: a background tab checks on return.
const REFRESH_MS = 15_000

/** Pilot spots, kept current while the page is open. Null until known (or
 * while the API is unreachable, when the page shows no count). */
export function usePilotSpots(): [PilotSpots | null, (left: number) => void] {
  const [spots, setSpots] = useState<PilotSpots | null>(null)
  const load = useCallback(() => {
    getPilotSpots().then(setSpots).catch(() => undefined)
  }, [])
  useEffect(() => {
    load()
    const timer = window.setInterval(() => document.visibilityState === 'visible' && load(), REFRESH_MS)
    const onShow = () => document.visibilityState === 'visible' && load()
    document.addEventListener('visibilitychange', onShow)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onShow)
    }
  }, [load])
  // A signup on this page counts at once, before the next check.
  const update = (left: number) => setSpots((s) => (s ? { ...s, left, taken: s.total - left } : s))
  return [spots, update]
}
