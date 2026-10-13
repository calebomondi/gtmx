import { useEffect, useState } from 'react'

import { getPilotSpots, type PilotSpots } from './api'

/** Pilot spots, fetched once. Null until known (or if the API is unreachable,
 * in which case the page simply doesn't show a count). */
export function usePilotSpots(): [PilotSpots | null, (left: number) => void] {
  const [spots, setSpots] = useState<PilotSpots | null>(null)
  useEffect(() => {
    getPilotSpots().then(setSpots).catch(() => undefined)
  }, [])
  const update = (left: number) => setSpots((s) => (s ? { ...s, left, taken: s.total - left } : s))
  return [spots, update]
}
