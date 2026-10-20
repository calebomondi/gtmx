import { useEffect, useState } from "react"

import { getSavedAcrossLaces, type SavedAcrossLacesDto } from "@/lib/api"

export interface SavedAcrossLaces {
  saved: SavedAcrossLacesDto | null
  error: string | null
}

/** What every live Lace has saved, for Home. Refetched when `refreshKey`
 * changes (new activity came in). */
export function useSavedAcrossLaces(refreshKey: string): SavedAcrossLaces {
  const [saved, setSaved] = useState<SavedAcrossLacesDto | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getSavedAcrossLaces()
      .then((next) => {
        if (cancelled) return
        setSaved(next)
        setError(null)
      })
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
    return () => { cancelled = true }
  }, [refreshKey])

  return { saved, error }
}
