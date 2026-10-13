import { useMemo, useState } from 'react'

import type { AccountRecord } from '@/lib/api'
import { VENUE_GROUP_LABEL, VENUE_GROUPS, venueGroupOfAccount, type VenueGroup } from '@/lib/buyer-type'

export type AccountKind = 'all' | 'company' | VenueGroup

export const KIND_LABEL: Record<AccountKind, string> = {
  all: 'All',
  company: 'Companies',
  ...VENUE_GROUP_LABEL,
}

export const KINDS: AccountKind[] = ['all', 'company', ...VENUE_GROUPS]

function kindOf(account: AccountRecord): Exclude<AccountKind, 'all'> {
  return venueGroupOfAccount(account.account_type) ?? 'company'
}

/** Companies are sold to; communities, creators and events are partnered
 * with, each in its own way. The chips only show when the list holds more
 * than one kind, so a B2B workspace keeps its plain list. Empty kinds are
 * left out. */
export function useAccountKinds(accounts: AccountRecord[]) {
  const [kind, setKind] = useState<AccountKind>('all')
  const counts = useMemo(() => {
    const tally = Object.fromEntries(KINDS.map((k) => [k, 0])) as Record<AccountKind, number>
    for (const account of accounts) tally[kindOf(account)] += 1
    tally.all = accounts.length
    return tally
  }, [accounts])
  const kinds = KINDS.filter((k) => k === 'all' || counts[k] > 0)
  const split = kinds.length > 2
  const active = split && kinds.includes(kind) ? kind : 'all'
  const visible = useMemo(
    () => (active === 'all' ? accounts : accounts.filter((a) => kindOf(a) === active)),
    [accounts, active],
  )
  return { kind: active, setKind, counts, kinds, split, visible }
}
