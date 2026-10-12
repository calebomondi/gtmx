import { useMemo, useState } from 'react'

import type { AccountRecord } from '@/lib/api'
import { isVenue } from '@/lib/buyer-type'

export type AccountKind = 'all' | 'company' | 'venue'

export const KIND_LABEL: Record<AccountKind, string> = {
  all: 'All',
  company: 'Companies',
  venue: 'Communities, creators & events',
}

export const KINDS: AccountKind[] = ['all', 'company', 'venue']

function matches(account: AccountRecord, kind: AccountKind): boolean {
  if (kind === 'all') return true
  return kind === 'venue' ? isVenue(account.account_type) : !isVenue(account.account_type)
}

/** Companies are sold to; venues are partnered with. The split only shows when
 * the list has both, so a B2B workspace keeps its plain list. */
export function useAccountKinds(accounts: AccountRecord[]) {
  const [kind, setKind] = useState<AccountKind>('all')
  const counts = useMemo(
    () => Object.fromEntries(KINDS.map((k) => [k, accounts.filter((a) => matches(a, k)).length])) as Record<AccountKind, number>,
    [accounts],
  )
  const split = counts.company > 0 && counts.venue > 0
  const active = split ? kind : 'all'
  const visible = useMemo(() => accounts.filter((a) => matches(a, active)), [accounts, active])
  return { kind: active, setKind, counts, split, visible }
}
