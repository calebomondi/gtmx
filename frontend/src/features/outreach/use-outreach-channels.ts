import { useEffect, useState } from 'react'

import { listConnections } from '@/lib/api'

import { CHANNEL_ORDER, CHANNELS, type Channel } from './outreach-types'

/** The outreach channels the user has a live account for. `null` while
 *  loading; an empty list when nothing is connected or the lookup failed. */
export function useConnectedChannels(): Channel[] | null {
  const [channels, setChannels] = useState<Channel[] | null>(null)
  useEffect(() => {
    let cancelled = false
    listConnections()
      .then(({ connections }) => {
        const live = new Set(connections.filter((c) => c.status === 'live').map((c) => c.platform))
        if (!cancelled) setChannels(CHANNEL_ORDER.filter((channel) => live.has(CHANNELS[channel].platform)))
      })
      .catch(() => {
        if (!cancelled) setChannels([])
      })
    return () => {
      cancelled = true
    }
  }, [])
  return channels
}
