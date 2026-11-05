import { useCallback, useEffect, useState } from "react"

import {
  linkLaceChannel,
  listAvailableChannels,
  listLaceChannels,
  unlinkLaceChannel,
  type ChannelAccountDto,
  type InboxPlatform,
  type LaceChannelDto,
} from "@/lib/api"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** The business accounts linked to a Lace, and linking more. */
export function useLaceChannels(laceId: string) {
  const [channels, setChannels] = useState<LaceChannelDto[]>([])
  const [choices, setChoices] = useState<{ platform: InboxPlatform; accounts: ChannelAccountDto[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listLaceChannels(laceId)
      .then((rows) => !cancelled && setChannels(rows))
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [laceId])

  const choose = useCallback(async (platform: InboxPlatform) => {
    setError(null)
    try {
      setChoices({ platform, accounts: await listAvailableChannels(laceId, platform) })
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  /** Link one; true when it is linked. */
  const link = useCallback(async (platform: InboxPlatform, accountId: string): Promise<boolean> => {
    try {
      const linked = await linkLaceChannel(laceId, platform, accountId)
      setChannels((prev) => [...prev, linked])
      setChoices(null)
      return true
    } catch (err) {
      setError(message(err))
      return false
    }
  }, [laceId])

  const unlink = useCallback(async (channelId: string) => {
    try {
      await unlinkLaceChannel(laceId, channelId)
      setChannels((prev) => prev.filter((c) => c.id !== channelId))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  return { channels, choices, loading, error, choose, link, unlink, cancel: () => setChoices(null) }
}
