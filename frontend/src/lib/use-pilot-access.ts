import { useCallback, useEffect, useState } from "react"

import { clearCurrentUserCache, getCurrentUser } from "@/lib/api"

/** checking until /users/me answers. The backend enforces the pilot on every
 * call; this only decides whether to show the app or the "not yet" page, so
 * a failed check shows the app (whose calls then say what's wrong). */
export type PilotAccess = "checking" | "in" | "out"

export function usePilotAccess(signedIn: boolean): { access: PilotAccess; recheck: () => void } {
  const [access, setAccess] = useState<PilotAccess>("checking")
  // Bumped to ask again, past the cached answer.
  const [version, setVersion] = useState(0)
  useEffect(() => {
    if (!signedIn) return
    let current = true
    getCurrentUser().then((me) => current && setAccess(me.in_pilot ? "in" : "out"),
                          () => current && setAccess("in"))
    return () => {
      current = false
    }
  }, [signedIn, version])
  const recheck = useCallback(() => {
    clearCurrentUserCache()
    setVersion((v) => v + 1)
  }, [])
  return { access, recheck }
}
