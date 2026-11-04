import { useState } from "react"

import { refreshLaceUnderstanding } from "@/lib/api"

export type RefreshState = "idle" | "asking" | "started" | "failed"

/** Asking the Lace to read its site and the web again. */
export function useRefreshUnderstanding(laceId: string) {
  const [state, setState] = useState<RefreshState>("idle")
  const [error, setError] = useState<string | null>(null)
  const refresh = async () => {
    setState("asking")
    setError(null)
    try {
      await refreshLaceUnderstanding(laceId)
      setState("started")
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setState("failed")
    }
  }
  return { state, error, refresh }
}
