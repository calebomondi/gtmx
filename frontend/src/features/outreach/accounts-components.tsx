import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Compass,
  ExternalLink,
  Loader2,
  MapPin,
  Sparkles,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

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
            {hasLinkedin && <img src="/linkedin.svg" alt="linkedin" className="size-4" />}
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
// Channel-aware composer
// ---------------------------------------------------------------------------

type ChannelKind = 'email' | 'linkedin' | 'x' | 'instagram' | 'tiktok'

interface Channel {
  kind: ChannelKind
  label: string
  address: string
  contactName?: string
}

const PLATFORM_CHANNELS: Record<string, { kind: ChannelKind; label: string }> = {
  linkedin: { kind: 'linkedin', label: 'LinkedIn' },
  instagram: { kind: 'instagram', label: 'Instagram' },
  tiktok: { kind: 'tiktok', label: 'TikTok' },
  x: { kind: 'x', label: 'X' },
  twitter: { kind: 'x', label: 'X' },
}

const CHANNEL_ICON: Record<ChannelKind, string> = {
  email: '/gmail.svg',
  linkedin: '/linkedin.svg',
  x: '',
  instagram: '/instagram.svg',
  tiktok: '/tiktok.svg',
}

function channelsFor(account: AccountRecord): Channel[] {
  const channels: Channel[] = []
  for (const raw of account.key_contacts) {
    const c = raw as { name?: string; title?: string; email?: string; linkedin?: string }
    if (typeof c.email === 'string' && c.email) {
      channels.push({ kind: 'email', label: 'Email', address: c.email, contactName: c.name })
    }
    if (typeof c.linkedin === 'string' && c.linkedin) {
      channels.push({ kind: 'linkedin', label: 'LinkedIn', address: c.linkedin, contactName: c.name })
    }
  }
  const platform = (account.platform ?? '').toLowerCase()
  const mapped = PLATFORM_CHANNELS[platform]
  if (mapped && !channels.some((ch) => ch.kind === mapped.kind)) {
    channels.push({ kind: mapped.kind, label: mapped.label, address: account.venue ?? account.name })
  }
  if (channels.length === 0) {
    channels.push({ kind: 'email', label: 'Email', address: '' })
  }
  return channels
}

const SEND_LABEL: Record<ChannelKind, string> = {
  email: 'Send email',
  linkedin: 'Send message',
  x: 'Send post',
  instagram: 'Send DM',
  tiktok: 'Send DM',
}

interface Composer {
  to: string
  subject: string
  draft: string
  agent: 'off' | 'drafting' | 'done'
  send: 'idle' | 'sending' | 'sent'
}

// Stub draft — grounded in what the run already knows about the account.
// Replaced by a real drafting endpoint when the outreach agent lands.
function stubDraft(account: AccountRecord, channel: Channel): { subject?: string; body: string } {
  const trigger = (account.trigger_event as { event?: string } | null)?.event
  const angle = account.why_reach_out[0]
  const first = channel.contactName?.split(' ')[0]
  const hello = first ? `Hi ${first},` : 'Hi there,'
  const reason = trigger ? `I saw ${trigger.charAt(0).toLowerCase()}${trigger.slice(1)}` : `I came across ${account.name}`
  const hook = angle ? `${angle.charAt(0).toLowerCase()}${angle.slice(1)}.` : ''
  const body = `${hello}\n\n${reason} — ${hook}\n\nWorth a quick conversation this week?\n\nBest,`
  return { subject: `Quick intro — ${account.name}`, body }
}

function AccountDetailDialog({
  account,
  open,
  onOpenChange,
  onToggleSelected,
}: {
  account: AccountRecord | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onToggleSelected: (a: AccountRecord) => void
}) {
  const channels = account ? channelsFor(account) : []
  const [channelIdx, setChannelIdx] = useState(0)
  const [dir, setDir] = useState(1) // switch direction for the composer transition
  const reduceMotion = useReducedMotion()
  // Per-channel composer state so switching channels never loses a draft.
  const [composers, setComposers] = useState<Record<number, Composer>>({})
  const agentTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const sendTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const channel = channels[Math.min(channelIdx, channels.length - 1)]
  const composer: Composer = (channel ? composers[channelIdx] : undefined) ?? {
    to: channel?.kind === 'email' ? channel.address : '',
    subject: '',
    draft: '',
    agent: 'off',
    send: 'idle',
  }
  const patch = (p: Partial<Composer>) =>
    setComposers((prev) => ({ ...prev, [channelIdx]: { ...composer, ...p } }))

  useEffect(() => () => {
    if (agentTimer.current) clearTimeout(agentTimer.current)
    if (sendTimer.current) clearTimeout(sendTimer.current)
  }, [])

  if (!account) return null

  const toggleAgent = () => {
    if (composer.agent === 'drafting') return
    if (composer.agent === 'done') {
      patch({ agent: 'off' })
      return
    }
    const idx = channelIdx
    patch({ agent: 'drafting', send: 'idle' })
    agentTimer.current = setTimeout(() => {
      const stub = stubDraft(account, channel)
      setComposers((prev) => {
        const cur = prev[idx] ?? composer
        return {
          ...prev,
          [idx]: {
            ...cur,
            subject: cur.subject || (channel.kind === 'email' ? (stub.subject ?? '') : cur.subject),
            draft: cur.draft || stub.body,
            agent: 'done',
          },
        }
      })
    }, 1500)
  }

  const onSend = () => {
    if (composer.send !== 'idle' || !composer.draft.trim()) return
    const idx = channelIdx
    patch({ send: 'sending' })
    sendTimer.current = setTimeout(() => {
      setComposers((prev) => ({ ...prev, [idx]: { ...(prev[idx] ?? composer), send: 'sent' } }))
    }, 900)
  }

  const composing = composer.agent === 'drafting'
  const sendDisabled = composing || composer.send !== 'idle' || !composer.draft.trim()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px] p-5">
        <DialogHeader className="px-0">
          <DialogTitle className={'text-lg'}>{account.name}</DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="secondary" className="capitalize">
              {account.account_type}
            </Badge>
            {account.industry && <span className="text-muted-foreground">· {account.industry}</span>}
            {account.geo && <span className="text-muted-foreground">· {account.geo}</span>}
            {account.score != null && (
              <span className="text-amber-500">· fit {Math.round(account.score * 100)}%</span>
            )}
          </DialogDescription>
        </DialogHeader>

        {channels.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <p className="text-xs font-medium uppercase tracking-wide text-foreground">
              Channel
            </p>
            <div className="flex flex-wrap gap-1.5">
              {channels.map((ch, i) => {
                const active = i === Math.min(channelIdx, channels.length - 1)
                return (
                  <button
                    key={`${ch.kind}-${ch.address}`}
                    type="button"
                    onClick={() => {
                      if (i === channelIdx) return
                      setDir(i > channelIdx ? 1 : -1)
                      setChannelIdx(i)
                    }}
                    className={cn(
                      'flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors',
                      active
                        ? 'border-amber-500 bg-amber-500/10 text-amber-500'
                        : 'border-border bg-secondary/50 text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                    )}
                  >
                    {CHANNEL_ICON[ch.kind] ? (
                      <img src={CHANNEL_ICON[ch.kind]} alt="" className="size-3.5" />
                    ) : (
                      <span className="grid size-3.5 place-items-center rounded bg-muted text-[9px] font-bold text-foreground">
                        X
                      </span>
                    )}
                    <span className="min-w-0 max-w-32 truncate">
                      {ch.contactName ?? ch.address ?? ch.label}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        <Separator className="my-3" />

        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={channelIdx}
            className="flex flex-col gap-3"
            initial={{ opacity: 0, x: dir * 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: dir * -16 }}
            transition={{ duration: reduceMotion ? 0 : 0.18, ease: 'easeOut' }}
          >
          {channel?.kind === 'email' && (
            <div className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2">
              <Label htmlFor="msg-to" className="text-xs text-muted-foreground">
                To
              </Label>
              <Input
                id="msg-to"
                value={composer.to}
                onChange={(e) => patch({ to: e.target.value })}
                placeholder="No email found — add one"
                className="h-8 text-xs"
              />
              <Label htmlFor="msg-subject" className="text-xs text-muted-foreground">
                Subject
              </Label>
              <Input
                id="msg-subject"
                value={composer.subject}
                onChange={(e) => patch({ subject: e.target.value })}
                placeholder="Add a subject"
                className="h-8 text-xs"
              />
            </div>
          )}

          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-muted-foreground">
              {channel
                ? `Message${channel.contactName ? ` to ${channel.contactName}` : ''} · ${channel.label}`
                : 'Message'}
            </p>
            {channel?.kind === 'x' && (
              <span className={cn('text-xs', composer.draft.length > 280 ? 'text-red-500' : 'text-muted-foreground')}>
                {composer.draft.length}/280
              </span>
            )}
          </div>

          <div className="relative">
            <Textarea
              value={composer.draft}
              onChange={(e) => patch({ draft: e.target.value })}
              placeholder={`Write your ${channel?.kind === 'email' ? 'email' : 'message'}…`}
              className="min-h-36 resize-none text-sm"
              disabled={composing}
            />
            {composing && (
              <div className="absolute inset-0 rounded-md border border-amber-500/40 bg-background/90 p-3">
                <div className="mb-2.5 flex items-center gap-1.5 text-xs text-amber-500">
                  <Sparkles className="size-3.5 animate-pulse" />
                  Drafting…
                </div>
                <Skeleton className="mb-2 h-3 w-11/12 bg-amber-500/15" />
                <Skeleton className="mb-2 h-3 w-4/5 bg-amber-500/15" />
                <Skeleton className="mb-2 h-3 w-3/5 bg-amber-500/15" />
                <Skeleton className="h-3 w-1/3 bg-amber-500/15" />
              </div>
            )}
          </div>

          <div className="flex items-center justify-between gap-2">
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    type="button"
                    size="sm"
                    variant={composer.agent === 'off' ? 'outline' : 'default'}
                    className={cn(
                      'cursor-pointer',
                      composer.agent !== 'off' && 'bg-amber-500 text-amber-950 hover:bg-amber-400',
                    )}
                    onClick={toggleAgent}
                    disabled={composing}
                  >
                    <Sparkles className="size-3.5" />
                    {composer.agent === 'drafting' ? 'Drafting…' : composer.agent === 'done' ? 'Agent (on)' : 'Agent'}
                  </Button>
                }
              />
              <TooltipContent>Let the agent draft the message</TooltipContent>
            </Tooltip>

            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="cursor-pointer"
                onClick={() => onToggleSelected(account)}
              >
                {account.selected ? 'Remove from shortlist' : 'Add to shortlist'}
              </Button>
              <Button
                type="button"
                size="sm"
                className={cn(
                  'cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400',
                  composer.send === 'sent' && 'bg-emerald-500 text-emerald-950 hover:bg-emerald-400',
                )}
                onClick={onSend}
                disabled={sendDisabled}
              >
                {composer.send === 'sending' && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
                {composer.send === 'sending'
                  ? 'Sending…'
                  : composer.send === 'sent'
                    ? 'Sent ✓'
                    : SEND_LABEL[channel?.kind ?? 'email']}
              </Button>
            </div>
          </div>
          </motion.div>
        </AnimatePresence>
      </DialogContent>
    </Dialog>
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
            <div className="flex flex-col gap-3">
              {accounts.map((account) => (
                <AccountCard key={account.id} account={account} onOpenDetail={setDetailAccount} />
              ))}
            </div>
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
          account={detailAccount}
          open={detailAccount !== null}
          onOpenChange={(open) => { if (!open) setDetailAccount(null) }}
          onToggleSelected={onToggleSelected}
        />
    </Card>
  )
}
