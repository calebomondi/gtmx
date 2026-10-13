import { useEffect, useState } from 'react'

import type { Competitor } from '@/features/competition/competition-types'
import { listAccounts, listCompetitors, type AccountRecord } from '@/lib/api'

import type { Signal } from './feed-types'

export type SignalSubject =
  | { kind: 'competitor'; competitor: Competitor }
  | { kind: 'account'; account: AccountRecord }
  | { kind: 'none' }

const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase()

/** The competitor or target account a feed item is about, looked up by name in
 * its workspace. `none` while loading, for other kinds of item, or when the
 * record has since been removed. */
export function useSignalSubject(signal: Signal, workspaceId: string | undefined): SignalSubject {
  const [subject, setSubject] = useState<{ id: string; value: SignalSubject }>({ id: '', value: { kind: 'none' } })

  useEffect(() => {
    if (!workspaceId || !signal.entity) return
    let cancelled = false
    const load = async () => {
      try {
        if (signal.category === 'competitor') {
          const { competitors } = await listCompetitors(workspaceId)
          const competitor = competitors.find((c) => same(c.name, signal.entity))
          if (!cancelled && competitor) setSubject({ id: signal.id, value: { kind: 'competitor', competitor } })
        } else if (signal.category === 'opportunity') {
          const { accounts } = await listAccounts(workspaceId)
          const account = accounts.find((a) => same(a.name, signal.entity))
          if (!cancelled && account) setSubject({ id: signal.id, value: { kind: 'account', account } })
        }
      } catch {
        // The dialog still shows the item itself; the details are a bonus.
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [signal.id, signal.category, signal.entity, workspaceId])

  return subject.id === signal.id ? subject.value : { kind: 'none' }
}
