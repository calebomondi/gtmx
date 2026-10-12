import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Compass,
  ExternalLink,
  Loader2,
  MapPin,
  Sparkles,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { AccountDetailDialog } from './account-dialog'
import { AccountKindFilter } from './account-kind-filter'
import { useAccountKinds } from './use-account-kinds'

import {
  getAccountRun,
  listAccountRuns,
  listAccounts,
  startAccountRun,
  updateAccount,
  type AccountRecord,
  type AccountRun,
} from '@/lib/api'

const LIVE_STATUSES = new Set(['pending', 'running'])
const POLL_MS = 1500

// ---------------------------------------------------------------------------
// Run controller
// ---------------------------------------------------------------------------

function useRunController(workspaceId: string | undefined, onSettled: () => void) {
  const [run, setRun] = useState<AccountRun | null>(null)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const onSettledRef = useRef(onSettled)
  onSettledRef.current = onSettled

  const start = useCallback(async () => {
    if (!workspaceId || starting) return
    setStarting(true)
    setStartError(null)
    try {
      const { run: started } = await startAccountRun(workspaceId)
      setRun(started)
      setRunId(started.id)
      if (!LIVE_STATUSES.has(started.status)) setRunId(null)
    } catch (exc) {
      setStartError(exc instanceof Error ? exc.message : 'Could not start the search.')
    } finally {
      setStarting(false)
    }
  }, [workspaceId, starting])

  // Adopt unfinished run on reload.
  useEffect(() => {
    if (!workspaceId) return
    let cancelled = false
    void (async () => {
      try {
        const runs = await listAccountRuns(workspaceId, 5)
        if (cancelled) return
        const live = runs.find((r) => LIVE_STATUSES.has(r.status))
        if (live) {
          setRunId(live.id)
          setRun(live)
        }
      } catch {}
    })()
    return () => {
      cancelled = true
    }
  }, [workspaceId])

  useEffect(() => {
    if (!runId || !workspaceId) return
    let cancelled = false
    const tick = async () => {
      try {
        const next = await getAccountRun(workspaceId, runId)
        if (cancelled) return
        setRun(next)
        if (!LIVE_STATUSES.has(next.status)) {
          setRunId(null)
          onSettledRef.current()
        }
      } catch {}
    }
    void tick()
    const timer = setInterval(() => void tick(), POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [runId, workspaceId])

  return { run, starting, startError, start }
}

// ---------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: AccountRun['status'] }) {
  const tone =
    status === 'completed'
      ? 'bg-emerald-500/15 text-emerald-500'
      : status === 'failed'
        ? 'bg-red-500/15 text-red-500'
        : 'bg-amber-500/15 text-amber-500'
  return (
    <Badge variant="outline" className={cn('border-transparent', tone)}>
      {status}
    </Badge>
  )
}

/** What the target does. Accounts found before the agent wrote summaries fall
 * back to their firmographics. */
function aboutLine(account: AccountRecord): string | null {
  if (account.summary?.trim()) return account.summary.trim()
  const parts = [account.industry, account.size, account.member_size && `${account.member_size} members`, account.event_date]
  const line = parts.filter((p): p is string => Boolean(p?.trim())).join(' · ')
  return line || null
}

function AccountCard({
  account,
  onOpenDetail,
}: {
  account: AccountRecord
  onOpenDetail: (a: AccountRecord) => void
}) {
  const trigger = account.trigger_event as { event?: string; source?: string } | null
  const hasEmail = account.key_contacts.some((c) => typeof (c as { email?: unknown }).email === 'string' && (c as { email?: unknown }).email)
  const hasLinkedin = account.key_contacts.some((c) => typeof (c as { linkedin?: unknown }).linkedin === 'string' && (c as { linkedin?: unknown }).linkedin)
  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onOpenDetail(account)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpenDetail(account) } } }
      className={cn(
        'cursor-pointer transition-colors',
        '!bg-amber-500/5 hover:!bg-amber-500/10',
        account.selected ? 'border-amber-500/60 ring-1 ring-amber-500/30' : 'hover:border-amber-500/40',
      )}
    >
      <CardHeader className="space-y-0">
        <CardTitle className="text-lg font-semibold">{account.name}</CardTitle>
        <div className="mt-1 flex w-full items-center justify-between gap-2 text-xs text-muted-foreground">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <Badge variant="secondary" className="capitalize">
              {account.account_type}
            </Badge>
            {account.do_not_contact && <Badge variant="destructive">Do not contact</Badge>}
            {account.geo && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-3" />
                {account.geo}
              </span>
            )}
            {account.platform && <span>· {account.platform}</span>}
            {account.score != null && (
              <span className="text-amber-500">· fit {Math.round(account.score * 100)}%</span>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-1.5">
            {hasEmail && <img src="/gmail.svg" alt="email" className="size-4" />}
            {(hasLinkedin || account.socials?.linkedin) && <img src="/linkedin.svg" alt="linkedin" className="size-4" />}
            {account.socials?.instagram && <img src="/instagram.svg" alt="instagram" className="size-4" />}
            {account.socials?.tiktok && <img src="/tiktok.svg" alt="tiktok" className="size-4" />}
          </div>
        </div>
        {aboutLine(account) && (
          <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{aboutLine(account)}</p>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3 pb-4 text-sm">
        {trigger?.event && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 p-2.5">
            <Sparkles className="mt-0.5 size-3.5 text-amber-500" />
            <p className="text-xs leading-relaxed">
              <span className="font-medium text-amber-500">Trigger</span>{' '}
              <span className="text-muted-foreground">{trigger.event}</span>
            </p>
          </div>
        )}
        {account.why_reach_out.length > 0 && (
          <ul className="flex list-disc flex-col gap-1 pl-4 text-xs leading-relaxed text-muted-foreground">
            {account.why_reach_out.slice(0, 3).map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        )}
        <div className="flex items-center justify-between gap-2">
          {account.website && (
            <a
              href={account.website}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-amber-500 hover:underline"
            >
              {account.domain ?? account.website}
              <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AccountsComponent({ workspaceId }: { workspaceId?: string }) {
  const [tab, setTab] = useState<'tracked' | 'runs'>('tracked')
  const [accounts, setAccounts] = useState<AccountRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [runs, setRuns] = useState<AccountRun[]>([])
  const [detailAccount, setDetailAccount] = useState<AccountRecord | null>(null)
  const historyKey = runs.length > 0 && runs[0].status === 'pending' ? 'live' : 'idle'

  const refreshAccounts = useCallback(async () => {
    if (!workspaceId) return
    try {
      const body = await listAccounts(workspaceId)
      setAccounts(body.accounts)
    } catch {}
    finally {
      setLoading(false)
    }
  }, [workspaceId])

  const refreshRuns = useCallback(async () => {
    if (!workspaceId) return
    try {
      const rows = await listAccountRuns(workspaceId, 25)
      setRuns(Array.isArray(rows) ? rows : [])
    } catch {}
  }, [workspaceId])

  useEffect(() => {
    void refreshAccounts()
    void refreshRuns()
  }, [refreshAccounts, refreshRuns, historyKey])

  const { run, starting, startError, start } = useRunController(workspaceId, () => {
    void refreshAccounts()
    void refreshRuns()
  })

  const onToggleSelected = useCallback(
    async (account: AccountRecord) => {
      if (!workspaceId) return
      const nextSelected = !account.selected
      setAccounts((prev) =>
        prev.map((a) => (a.id === account.id ? { ...a, selected: nextSelected } : a)),
      )
      try {
        await updateAccount(workspaceId, account.id, { selected: nextSelected })
      } catch {
        void refreshAccounts()
      }
    },
    [workspaceId, refreshAccounts],
  )

  const hunting = starting || (run != null && LIVE_STATUSES.has(run.status))
  const kinds = useAccountKinds(accounts)

  return (
    <Card className="flex min-h-0 flex-1 flex-col">
      <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="text-base font-semibold">Target accounts</CardTitle>
          <CardDescription className="text-xs">
            Accounts matched to your ICP — select the ones to reach out to.
          </CardDescription>
        </div>
      </CardHeader>

      {run && LIVE_STATUSES.has(run.status) && (
        <div className="mx-4 mb-2 flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin text-amber-500" />
          <span>
            Hunting accounts… {run.candidates_seen > 0 ? `· ${run.candidates_seen} sources checked` : ''}
            {run.found > 0 ? ` · ${run.found} found` : ''}
          </span>
        </div>
      )}
      {run && run.status === 'failed' && (
        <p className="mx-4 mb-2 text-xs text-red-500">{run.error ?? 'The run failed.'}</p>
      )}
      {startError && <p className="mx-4 mb-2 text-xs text-red-500">{startError}</p>}

      <CardContent className="flex min-h-0 flex-1 flex-col">
        <div className="mb-3 flex items-center justify-between gap-1.5">
          <div className="flex items-center justify-center gap-1.5">
            {(
              [
                { value: 'tracked' as const, label: 'Targets' },
                { value: 'runs' as const, label: `Runs ${runs.length ? `(${runs.length})` : ''}` },
              ] as const
            ).map((chip) => (
              <button
                key={chip.value}
                type="button"
                disabled={hunting}
                onClick={() => setTab(chip.value)}
                className={cn(
                  'cursor-pointer rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                  tab === chip.value
                    ? 'border-amber-500 bg-amber-500 text-amber-950'
                    : 'border-border bg-secondary text-secondary-foreground hover:bg-accent hover:text-accent-foreground',
                )}
              >
                {chip.label}
              </button>
            ))}
          </div>
          <Button
            size="sm"
            className="bg-amber-500 text-amber-950 hover:bg-amber-400"
            onClick={start}
            disabled={hunting}
          >
            {hunting ? (
              <Loader2 className="mr-1.5 size-3.5 animate-spin" />
            ) : (
              <Compass className="mr-1.5 size-3.5" />
            )}
            Find accounts
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === 'tracked' ? (
          loading && accounts.length === 0 ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          ) : accounts.length === 0 ? (
            <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-4 py-10 text-center">
              <Compass className="size-5 text-muted-foreground" />
              <p className="text-sm font-medium">No accounts yet</p>
              <p className="max-w-sm text-xs text-muted-foreground">
                Hit <span className="font-medium">Find accounts</span> to have the agent search for
                target companies and channels matching your ICP.
              </p>
            </div>
          ) : (
            <>
              {kinds.split && (
                <AccountKindFilter kind={kinds.kind} counts={kinds.counts} onChange={kinds.setKind} />
              )}
              <div className="flex flex-col gap-3">
                {kinds.visible.map((account) => (
                  <AccountCard key={account.id} account={account} onOpenDetail={setDetailAccount} />
                ))}
              </div>
            </>
          )
        ) : runs.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">No account runs yet.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {runs.map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
                <div className="min-w-0">
                  <p className="text-xs font-medium">
                    {new Date(r.created_at).toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {r.found} found · {r.candidates_seen} checked
                  </p>
                </div>
                <StatusBadge status={r.status} />
              </div>
            ))}
          </div>
        )}
        </div>
      </CardContent>
        <AccountDetailDialog
          key={detailAccount?.id ?? 'none'}
          workspaceId={workspaceId}
          account={detailAccount}
          open={detailAccount !== null}
          onOpenChange={(open) => { if (!open) setDetailAccount(null) }}
          onToggleSelected={onToggleSelected}
        />
    </Card>
  )
}
