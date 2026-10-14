import { useEffect, useState } from 'react'

import { assessAccountFit, getRun, listAccounts, type AccountFit, type AccountRecord } from '@/lib/api'

const POLL_MS = 3000
const DONE = new Set(['completed', 'failed', 'cancelled'])

export type FitState =
  | { status: 'ready'; fit: AccountFit }
  | { status: 'assessing' }
  | { status: 'unavailable' }

/** The account's fit, assessing it on demand when it predates fit
 * assessment: one workspace-wide run, polled until it finishes. */
export function useAccountFit(workspaceId: string | undefined, account: AccountRecord): FitState {
  const [state, setState] = useState<{ id: string; value: FitState }>({ id: '', value: { status: 'assessing' } })

  useEffect(() => {
    if (account.fit || !workspaceId) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const settle = (value: FitState) => {
      if (!cancelled) setState({ id: account.id, value })
    }
    const poll = async (runId: string) => {
      try {
        const run = await getRun(runId)
        if (!DONE.has(run.status)) {
          timer = setTimeout(() => void poll(runId), POLL_MS)
          return
        }
        const { accounts } = await listAccounts(workspaceId)
        const fit = accounts.find((a) => a.id === account.id)?.fit
        settle(fit ? { status: 'ready', fit } : { status: 'unavailable' })
      } catch {
        settle({ status: 'unavailable' })
      }
    }
    assessAccountFit(workspaceId).then((run) => void poll(run.id), () => settle({ status: 'unavailable' }))
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [workspaceId, account.id, account.fit])

  if (account.fit) return { status: 'ready', fit: account.fit }
  return state.id === account.id ? state.value : { status: 'assessing' }
}
