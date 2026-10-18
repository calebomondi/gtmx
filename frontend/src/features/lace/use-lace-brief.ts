import { useCallback, useEffect, useState } from "react"

import { getLaceBrief, updateLaceBrief, type BriefSettingsDto } from "@/lib/api"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** When a Lace posts its brief, and changing it. */
export function useLaceBrief(laceId: string) {
  const [settings, setSettings] = useState<BriefSettingsDto | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getLaceBrief(laceId)
      .then((row) => !cancelled && setSettings(row))
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [laceId])

  const update = useCallback(async (changes: Parameters<typeof updateLaceBrief>[1]) => {
    setError(null)
    try {
      setSettings(await updateLaceBrief(laceId, changes))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  return { settings, loading, error, update }
}
