import { useCallback, useEffect, useState } from "react"

import {
  getJurisdiction, listLaceRegulations, setJurisdiction, setLaceRegulationStatus,
  type JurisdictionDto, type LaceRegulationDto,
} from "@/lib/api"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export interface LaceRegulations {
  jurisdiction: JurisdictionDto | null
  /** What the Lace watches. */
  tracked: LaceRegulationDto[]
  /** Found by a search, waiting for the founder. */
  suggested: LaceRegulationDto[]
  loading: boolean
  error: string | null
  track: (id: string) => Promise<void>
  dismiss: (id: string) => Promise<void>
  /** Confirm where the startup is registered and operates. False when it didn't save. */
  confirm: (registeredIn: string | null, operatesIn: string[]) => Promise<boolean>
}

/** A Lace's jurisdiction and its regulations. Refetched when `refreshKey`
 * changes (a search finished, a bill moved). */
export function useLaceRegulations(laceId: string, refreshKey = ""): LaceRegulations {
  const [jurisdiction, setPlace] = useState<JurisdictionDto | null>(null)
  const [tracked, setTracked] = useState<LaceRegulationDto[]>([])
  const [suggested, setSuggested] = useState<LaceRegulationDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([getJurisdiction(laceId), listLaceRegulations(laceId, "tracked"), listLaceRegulations(laceId, "suggested")])
      .then(([place, watched, waiting]) => {
        if (cancelled) return
        setPlace(place)
        setTracked(watched)
        setSuggested(waiting)
      })
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [laceId, refreshKey])

  const track = useCallback(async (id: string) => {
    try {
      const saved = await setLaceRegulationStatus(laceId, id, "tracked")
      setSuggested((prev) => prev.filter((r) => r.id !== id))
      setTracked((prev) => [...prev, saved])
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const dismiss = useCallback(async (id: string) => {
    try {
      await setLaceRegulationStatus(laceId, id, "dismissed")
      setTracked((prev) => prev.filter((r) => r.id !== id))
      setSuggested((prev) => prev.filter((r) => r.id !== id))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const confirm = useCallback(async (registeredIn: string | null, operatesIn: string[]) => {
    try {
      setPlace(await setJurisdiction(laceId, registeredIn, operatesIn))
      setError(null)
      return true
    } catch (err) {
      setError(message(err))
      return false
    }
  }, [laceId])

  return { jurisdiction, tracked, suggested, loading, error, track, dismiss, confirm }
}
