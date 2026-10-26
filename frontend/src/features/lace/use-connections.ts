import { useCallback, useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { listConnections, type ChannelDto, type ConnectionDto } from "@/lib/api"
import { PLATFORM_LABEL, type Platform } from "@/lib/platforms"

export interface Connections {
  connections: ConnectionDto[]
  /** Channels that can be connected now (the rest need app-level setup). */
  channels: ChannelDto[]
  loading: boolean
  error: string | null
  /** Re-list; resolves to the connections, or null when listing failed. */
  reload: () => Promise<ConnectionDto[] | null>
}

/** The user's connected accounts. Back from connecting one (the URL carries
 * ?connected=<platform>), it re-lists from the server, which never trusts
 * that parameter, says whether it worked, and drops the parameter. */
export function useConnections(): Connections {
  const [connections, setConnections] = useState<ConnectionDto[]>([])
  const [channels, setChannels] = useState<ChannelDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const returnedFrom = params.get("connected") as Platform | null

  const reload = useCallback(async () => {
    try {
      const state = await listConnections()
      setConnections(state.connections)
      setChannels(state.channels)
      setError(null)
      return state.connections
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const listed = await reload()
      if (cancelled || !returnedFrom || !(returnedFrom in PLATFORM_LABEL)) return
      const live = listed?.some((c) => c.platform === returnedFrom && c.status === "live")
      if (live) toast.success(`${PLATFORM_LABEL[returnedFrom]} connected`)
      else toast.info(`${PLATFORM_LABEL[returnedFrom]} sign-in didn't finish`, { description: "Try connecting again." })
      setParams((prev) => {
        prev.delete("connected")
        return prev
      }, { replace: true })
    })()
    return () => { cancelled = true }
  }, [reload, returnedFrom, setParams])

  return { connections, channels, loading, error, reload }
}
