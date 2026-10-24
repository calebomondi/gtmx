import { useCallback, useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { listLaceAppActions, listLaceApps, updateLaceApp, type AppActionDto, type LaceAppDto } from "@/lib/api"
import { PLATFORM_LABEL, type Platform } from "@/lib/platforms"

// How often the actions waiting for the founder are looked at again.
const POLL_MS = 30_000

export interface LaceApps {
  /** Every app, as this Lace sees it; null until first loaded. */
  apps: LaceAppDto[] | null
  /** What the Lace proposed doing in the apps, newest first. */
  actions: AppActionDto[]
  /** Proposals waiting for the founder's click. */
  waiting: number
  error: string | null
  refresh: () => Promise<void>
  setEnabled: (platform: Platform, enabled: boolean) => Promise<void>
}

/** A Lace's apps and its app actions. The apps (read live from the founder's
 * connections) load when `open` (its settings); the actions are kept current
 * all along, for the Feed. Coming back from connecting an app from this Lace
 * (?connected=<platform>) switches it on for this Lace. */
export function useLaceApps(laceId: string, open: boolean): LaceApps {
  const [apps, setApps] = useState<LaceAppDto[] | null>(null)
  const [actions, setActions] = useState<AppActionDto[]>([])
  const [error, setError] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()

  const loadActions = useCallback(async () => {
    setActions(await listLaceAppActions(laceId))
  }, [laceId])

  const refresh = useCallback(async () => {
    try {
      const [nextApps] = await Promise.all([listLaceApps(laceId), loadActions()])
      setApps(nextApps)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [laceId, loadActions])

  useEffect(() => {
    // A missed look is retried on the next tick.
    const look = () => void loadActions().catch(() => undefined)
    look()
    const timer = setInterval(look, POLL_MS)
    return () => clearInterval(timer)
  }, [loadActions])

  useEffect(() => {
    if (open) void refresh()
  }, [open, refresh])

  const setEnabled = useCallback(async (platform: Platform, enabled: boolean) => {
    try {
      const saved = await updateLaceApp(laceId, platform, { enabled })
      setApps((prev) => prev?.map((a) => (a.platform === platform ? saved : a)) ?? prev)
    } catch (err) {
      toast.error(`Couldn't change ${PLATFORM_LABEL[platform]}`, { description: err instanceof Error ? err.message : String(err) })
    }
  }, [laceId])

  const connected = params.get("connected") as Platform | null
  useEffect(() => {
    if (!connected || !(connected in PLATFORM_LABEL)) return
    setParams((prev) => {
      prev.delete("connected")
      return prev
    }, { replace: true })
    void (async () => {
      try {
        const live = (await listLaceApps(laceId)).find((a) => a.platform === connected)?.connected
        if (live) {
          await setEnabled(connected, true)
          toast.success(`${PLATFORM_LABEL[connected]} connected`)
        } else {
          toast.info(`${PLATFORM_LABEL[connected]} sign-in didn't finish`, { description: "Try connecting again." })
        }
      } finally {
        await refresh()
      }
    })()
  }, [laceId, connected, setParams, setEnabled, refresh])

  return { apps, actions, waiting: actions.filter((a) => a.status === "proposed").length, error, refresh, setEnabled }
}
