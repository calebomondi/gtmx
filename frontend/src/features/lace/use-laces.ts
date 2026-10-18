import { useEffect, useState } from "react"

import { listLaces, type LaceDto } from "@/lib/api"

export function useLaces(): { laces: LaceDto[]; loading: boolean; error: string | null } {
  const [laces, setLaces] = useState<LaceDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    listLaces()
      .then((rows) => !cancelled && setLaces(rows))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])
  return { laces, loading, error }
}
