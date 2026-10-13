import { useEffect, useState } from 'react'

import { listAccounts, type AccountRecord } from '@/lib/api'
import { VENUE_GROUPS, venueGroupOfAccount, type VenueGroup } from '@/lib/buyer-type'

export type VenuesByGroup = Record<VenueGroup, AccountRecord[]>

const empty = (): VenuesByGroup => ({ community: [], creator: [], event: [] })

/** The communities, creators and events found as targets in this workspace,
 * grouped. Loaded once; empty until (and unless) account discovery has run. */
export function useVenueAccounts(workspaceId: string | undefined, enabled: boolean): VenuesByGroup {
  const [venues, setVenues] = useState<{ id: string | undefined; groups: VenuesByGroup }>({ id: undefined, groups: empty() })

  useEffect(() => {
    if (!workspaceId || !enabled) return
    let cancelled = false
    listAccounts(workspaceId)
      .then(({ accounts }) => {
        if (cancelled) return
        const groups = empty()
        for (const account of accounts) {
          const group = venueGroupOfAccount(account.account_type)
          if (group) groups[group].push(account)
        }
        for (const group of VENUE_GROUPS) groups[group].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        setVenues({ id: workspaceId, groups })
      })
      .catch(() => {
        // The ICP's own channels still show; found venues are an addition.
      })
    return () => {
      cancelled = true
    }
  }, [workspaceId, enabled])

  return venues.id === workspaceId ? venues.groups : empty()
}
