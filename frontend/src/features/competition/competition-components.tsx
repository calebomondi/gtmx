import {
  useCallback,
  useEffect,
  useEffectEvent,
  useMemo,
  useState,
} from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  History,
  Loader2,
  Plus,
  Radar,
  Search,
  XCircle,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { emitSignal } from '@/features/feed/feed-store'
import {
  ApiError,
  addCompetitor,
  deleteCompetitor,
  getCompetitorRun,
  listCompetitorRuns,
  listCompetitors,
  startCompetitorRun,
  updateCompetitor,
} from '@/lib/api'
import { ensureInsightsLoaded, useInsights } from '@/lib/insights-store'
import { cn } from 'cn'

import { CompetitorCard } from './competitor-card'
import {
  dropReasonLabel,
  type Competitor,
  type CompetitorRun,
} from './competition-types'

/**
 * THE COMPETITORS TAB, AND WHY IT IS SEPARATE FROM THE OFFER TAB
 * -------------------------------------------------------------
 * Two standards of knowledge live in this product, and keeping them in
 * different tabs is the honest arrangement rather than a filing convenience:
 *
 *   Offer > Competition   holds the competition stage's IDEAL COMPETITOR PROFILE
 *                         -- archetypes, pricing anchors, entry signals. It is a
 *                         construct. It names no company, and the stage was
 *                         rebuilt to make it aggressive, because a construct
 *                         cannot be false.
 *
 *   Competitors (this tab) holds REAL COMPANIES. Every field is a claim about a
 *                         named business, so every one of them carries the quote
 *                         it came from, and a company with no public website is
 *                         dropped rather than stored. This is where the standard
 *                         inverts: aggression here would be fabrication.
 *
 * Seeding this tab from the archetypes was considered and rejected -- a row
 * built from an archetype is indistinguishable, on screen, from a fabricated
 * company. That is precisely the confusion the separation exists to prevent.
 *
 * The tab is also the only surface that talks to the competitor API. The agent
 * runs from a workspace rather than from the discovery session, so this tab
 * polls a run rather than listening on the discovery socket.
 */

// How often the watch list is re-read while something is in flight. Fast enough
// that a run finishing feels immediate, slow enough that a two-minute hunt is
// not 48 requests.
const POLL_MS = 2500
// A manual add researches the site's page in the background, which is one LLM
// call plus a fetch. Past this it is not coming, and leaving the card spinning
// forever would be a lie about work that stopped.
const MANUAL_RESEARCH_TIMEOUT_MS = 180_000

const LIVE_STATUSES = new Set(['pending', 'running'])

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------

function useCompetitors(workspaceId: string | undefined) {
  const [competitors, setCompetitors] = useState<Competitor[]>([])
  const [error, setError] = useState<string | null>(null)
  // Which workspace the current `competitors` belong to. `loading` is derived
  // from it rather than tracked as its own flag, so switching workspaces cannot
  // leave the previous one's rows on screen next to a spinner that already
  // stopped -- the two are wrong together by construction.
  const [loadedFor, setLoadedFor] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!workspaceId) {
      setCompetitors([])
      setLoadedFor(null)
      return
    }
    try {
      const body = await listCompetitors(workspaceId)
      setCompetitors(Array.isArray(body?.competitors) ? body.competitors : [])
      setError(null)
    } catch (exc) {
      setError(
        exc instanceof ApiError ? exc.message : 'Could not load the watch list.',
      )
    } finally {
      setLoadedFor(workspaceId)
    }
  }, [workspaceId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const loading = workspaceId !== undefined && loadedFor !== workspaceId

  return { competitors, setCompetitors, loading, error, refresh }
}

// ---------------------------------------------------------------------------
// Run control
// ---------------------------------------------------------------------------

/** The live run, if this tab started or adopted one.
 *
 * Held as an id rather than the row itself so the polled row always replaces
 * it. A run object captured at start time would sit at `pending` forever no
 * matter what the server did with it. */
function useLiveRun(workspaceId: string | undefined, onSettled: () => void) {
  const [runId, setRunId] = useState<string | null>(null)
  const [run, setRun] = useState<CompetitorRun | null>(null)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  // How many of the rows this run found were already on the list. Reported by
  // the start call only — the polled run row does not carry it — and the reason
  // it matters is that without it a re-run that found nothing new and a first
  // run that found nothing are the same screen: an unchanged list.
  const [alreadyTracked, setAlreadyTracked] = useState<number | null>(null)
  // The poll effect deliberately does not depend on `onSettled`: the caller
  // passes a fresh closure each render, and including it would tear the
  // interval down and rebuild it on every tick of the parent.
  const onSettledRef = useEffectEvent(onSettled)

  const start = useCallback(async () => {
    if (!workspaceId || starting) return
    setStarting(true)
    setStartError(null)
    try {
      const { run: started, already_tracked } = await startCompetitorRun(workspaceId)
      setRun(started)
      setAlreadyTracked(already_tracked)
      setRunId(started.id)
      // An already-pending run is returned rather than a second one started, so
      // adopting it here is the only correct move — pressing the button again
      // would otherwise appear to do nothing at all.
      if (!LIVE_STATUSES.has(started.status)) setRunId(null)
    } catch (exc) {
      setStartError(
        exc instanceof ApiError
          ? exc.message
          : 'Could not start the search. Try again in a moment.',
      )
    } finally {
      setStarting(false)
    }
  }, [workspaceId, starting])

  // Adopt an unfinished run left over from a page reload, so closing the tab
  // mid-hunt does not leave a hunt that can only be watched by refreshing.
  useEffect(() => {
    if (!workspaceId) return
    let cancelled = false
    void (async () => {
      try {
        const runs = await listCompetitorRuns(workspaceId, 5)
        if (cancelled) return
        const live = runs.find((r) => LIVE_STATUSES.has(r.status))
        if (live) {
          setRunId(live.id)
          setRun(live)
        }
      } catch {
        // A failed adoption poll is not worth surfacing; the run button still
        // works and the user can start a fresh run.
      }
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
        const next = await getCompetitorRun(workspaceId, runId)
        if (cancelled) return
        setRun(next)
        if (!LIVE_STATUSES.has(next.status)) {
          setRunId(null)
          onSettledRef()
        }
      } catch {
        // A dropped poll is not a failed run. The next tick tries again, and the
        // run row itself keeps the real outcome either way.
      }
    }

    void tick()
    const timer = setInterval(() => void tick(), POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [runId, workspaceId])

  return {
    run,
    runId,
    starting,
    start,
    startError,
    alreadyTracked,
    clearStartError: () => setStartError(null),
  }
}

function useRunHistory(workspaceId: string | undefined, refreshKey: number) {
  const [runs, setRuns] = useState<CompetitorRun[]>([])
  // Which key the current rows belong to, so `loading` is derived rather than
  // tracked. `refreshKey` changes when a run settles, which is precisely the
  // moment the history is stale.
  const [loadedFor, setLoadedFor] = useState<string | null>(null)
  const key = workspaceId === undefined ? null : `${workspaceId}:${refreshKey}`

  useEffect(() => {
    if (!workspaceId) {
      setRuns([])
      setLoadedFor(null)
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const res = await listCompetitorRuns(workspaceId, 25)
        setRuns(Array.isArray(res) ? res : [])
      } catch {
        setRuns([])
      } finally {
        if (!cancelled) setLoadedFor(key)
      }
    })()
    return () => {
      cancelled = true
    }
    // `key` is derived from the two values it is built from, and is included so
    // a change to either re-reads the history.
  }, [workspaceId, key])

  return { runs: Array.isArray(runs) ? runs : [], loading: key !== null && loadedFor !== key }
}

/** Ids of manually-added rows whose first site read has not landed yet.
 *
 * Kept out of the `Competitor` type on purpose: "the background task is still
 * running" is a property of this screen's session, not of the row, and a
 * reload should not leave a card claiming to be researching forever. The cap
 * is what guarantees that. */
function useManualResearchPolling(
  competitors: Competitor[],
  refresh: () => Promise<void>,
) {
  const [tracked, setTracked] = useState<string[]>([])
  const track = useCallback((id: string) => {
    setTracked((prev) => (prev.includes(id) ? prev : [...prev, id]))
  }, [])

  // Derived during render rather than stored and reconciled in an effect: a
  // tracked id stops being pending the moment the server stamps it researched,
  // or the moment its row leaves the list, and there is no window in between
  // where the two could disagree.
  const pending = useMemo(() => {
    const byId = new Map(competitors.map((c) => [c.id, c]))
    return new Set(
      tracked.filter((id) => byId.get(id)?.deep_researched_at === null),
    )
  }, [tracked, competitors])

  // A boolean rather than the set itself, because the set is a fresh identity on
  // every poll and keying the effect on it would tear the interval down and
  // rebuild it each time -- which, since the first tick is one POLL_MS away,
  // means the interval never actually fires.
  const researching = pending.size > 0
  useEffect(() => {
    if (!researching) return
    const timer = setInterval(() => void refresh(), POLL_MS)
    // The give-up point: a background read that has not landed in three minutes
    // is not coming, and a card claiming to be researching forever would be a
    // lie about work that stopped. A timer rather than a comparison inside the
    // effect, so the deadline actually fires.
    const giveUp = setTimeout(
      () => setTracked([]),
      MANUAL_RESEARCH_TIMEOUT_MS,
    )
    return () => {
      clearInterval(timer)
      clearTimeout(giveUp)
    }
  }, [researching, refresh])

  return { track, pending }
}

// ---------------------------------------------------------------------------
// Run status strip
// ---------------------------------------------------------------------------

function RunStatusStrip({
  run,
  alreadyTracked,
  onDismiss,
}: {
  run: CompetitorRun
  /** From the start call, which is the only response that carries it. Null for a
   * run this tab merely adopted after a reload, where saying nothing is the
   * honest answer rather than guessing at zero. */
  alreadyTracked: number | null
  onDismiss: () => void
}) {
  const live = LIVE_STATUSES.has(run.status)
  const reasons = Object.entries(run.dropped_reasons ?? {})

  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-xl border p-3',
        run.status === 'failed'
          ? 'border-destructive/40 bg-destructive/5'
          : live
            ? 'border-amber-500/30 bg-amber-500/5'
            : 'border-border bg-muted/30',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {live ? (
            <Loader2 className="size-4 shrink-0 animate-spin text-amber-500" />
          ) : run.status === 'failed' ? (
            <XCircle className="size-4 shrink-0 text-destructive" />
          ) : (
            <CheckCircle2 className="size-4 shrink-0 text-emerald-500" />
          )}
          <span className="text-[13px] font-medium text-foreground">
            {live
              ? run.status === 'pending'
                ? 'Queued — the search is about to start'
                : `Searching your ${run.archetypes_targeted} competitor archetype${run.archetypes_targeted === 1 ? '' : 's'}`
              : run.status === 'failed'
                ? 'The search failed'
                : 'Search finished'}
          </span>
        </div>
        {!live && (
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="cursor-pointer text-muted-foreground"
            onClick={onDismiss}
            aria-label="Dismiss run result"
          >
            <span aria-hidden>&times;</span>
          </Button>
        )}
      </div>

      {run.status === 'failed' && run.error && (
        <p className="text-[12px] leading-relaxed text-destructive/90">
          {run.error}
        </p>
      )}

      {run.status === 'completed' && (
        <div className="flex flex-col gap-2">
          <p className="text-[12px] leading-relaxed text-foreground/85">
            Looked at <strong className="tabular-nums">{run.candidates_seen}</strong>{' '}
            candidates and tracked{' '}
            <strong className="tabular-nums">{run.found}</strong>, dropping{' '}
            <strong className="tabular-nums">{run.dropped}</strong>.
          </p>
          {/* Without this, a re-run that found nothing new and a first run that
              found nothing show the same unchanged list. The counts alone say
              "found N" either way, so the difference has to be spelled out. */}
          {alreadyTracked !== null && alreadyTracked > 0 && run.found <= alreadyTracked && (
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              All {alreadyTracked} of them were already on your watch list, so
              nothing new was added &mdash; their profiles were refreshed
              instead.
            </p>
          )}
          {reasons.length > 0 && (
            <details className="text-[12px] text-muted-foreground">
              <summary className="cursor-pointer text-foreground/80 hover:text-foreground">
                Why the rest were dropped
              </summary>
              <ul className="mt-1.5 flex flex-col gap-1">
                {reasons
                  .sort((a, b) => b[1] - a[1])
                  .map(([reason, count]) => (
                    <li key={reason} className="flex gap-2 leading-relaxed">
                      <span className="shrink-0 tabular-nums text-muted-foreground/70">
                        {count}&times;
                      </span>
                      <span>{dropReasonLabel(reason)}</span>
                    </li>
                  ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Run history
// ---------------------------------------------------------------------------

function RunRow({ run }: { run: CompetitorRun }) {
  const live = LIVE_STATUSES.has(run.status)
  const when = new Date(run.created_at)
  const reasons = Object.entries(run.dropped_reasons ?? {})

  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-border/60 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[12px] font-medium text-foreground/90">
          {live ? (
            <Loader2 className="size-3 animate-spin text-amber-500" />
          ) : run.status === 'failed' ? (
            <XCircle className="size-3 text-destructive" />
          ) : (
            <CheckCircle2 className="size-3 text-emerald-500" />
          )}
          {Number.isNaN(when.getTime())
            ? 'a previous run'
            : when.toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
        </span>
        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-[11px] font-medium capitalize',
            live
              ? 'bg-amber-500/15 text-amber-500'
              : run.status === 'failed'
                ? 'bg-destructive/15 text-destructive'
                : 'bg-muted text-muted-foreground',
          )}
        >
          {run.status}
        </span>
      </div>
      {run.status === 'completed' && (
        <p className="text-[12px] text-muted-foreground">
          {run.candidates_seen} seen &middot; {run.found} tracked &middot;{' '}
          {run.dropped} dropped
          {reasons.length > 0 && (
            <>
              {' '}
              &mdash;{' '}
              {reasons
                .sort((a, b) => b[1] - a[1])
                .map(([reason, count]) => `${count} ${dropReasonLabel(reason)}`)
                .join('; ')}
            </>
          )}
        </p>
      )}
      {run.status === 'failed' && run.error && (
        <p className="text-[12px] leading-relaxed text-destructive/90">
          {run.error}
        </p>
      )}
    </div>
  )
}

function RunHistory({
  runs,
  loading,
}: {
  runs: CompetitorRun[]
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-[13px] text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin" />
        Loading past searches
      </div>
    )
  }
  const safeRuns = Array.isArray(runs) ? runs : []
  if (safeRuns.length === 0) {
    return (
      <p className="py-10 text-center text-[13px] text-muted-foreground">
        No searches yet.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      {safeRuns.map((run) => (
        <RunRow key={run.id} run={run} />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

function AddCompetitorDialog({
  workspaceId,
  open,
  onOpenChange,
  onAdded,
}: {
  workspaceId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdded: (competitor: Competitor) => void
}) {
  const [website, setWebsite] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!website.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      const competitor = await addCompetitor(workspaceId, {
        website: website.trim(),
        name: name.trim() || undefined,
      })
      setWebsite('')
      setName('')
      onOpenChange(false)
      onAdded(competitor)
    } catch (exc) {
      setError(
        exc instanceof ApiError ? exc.message : 'Could not add that competitor.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a competitor</DialogTitle>
          <DialogDescription>
            Give the company&rsquo;s website. The agent reads the site and fills
            in who they serve, pricing, weaknesses, customer sentiment, pain
            signals and socials &mdash; everything except what it cannot verify,
            which it will mark as not found rather than guess at.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="competitor-website">Website</Label>
            <Input
              id="competitor-website"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="acme.com"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') void submit()
              }}
            />
            <span className="text-[11px] text-muted-foreground">
              A website is required &mdash; a competitor with no public site
              cannot be verified.
            </span>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="competitor-name">Name (optional)</Label>
            <Input
              id="competitor-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Read off the site if you leave this blank"
            />
          </div>
          {error && (
            <p className="flex items-start gap-1.5 text-[12px] leading-relaxed text-destructive">
              <AlertTriangle className="mt-0.5 size-3 shrink-0" />
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            className="cursor-pointer"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            className="cursor-pointer"
            onClick={() => void submit()}
            disabled={!website.trim() || busy}
          >
            {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
            Add and research
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function EditCompetitorDialog({
  workspaceId,
  competitor,
  onClose,
  onSaved,
}: {
  workspaceId: string
  competitor: Competitor
  onClose: () => void
  onSaved: (competitor: Competitor) => void
}) {
  const [name, setName] = useState(competitor.name)
  const [website, setWebsite] = useState(competitor.website)
  const [targetCustomers, setTargetCustomers] = useState(competitor.target_customers ?? '')
  const [headquarters, setHeadquarters] = useState(competitor.headquarters ?? '')
  const [scope, setScope] = useState(competitor.geography_scope ?? '')
  const [notes, setNotes] = useState(competitor.notes ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const save = async () => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const saved = await updateCompetitor(
        workspaceId,
        competitor.id,
        {
          name: name.trim() || null,
          website: website.trim() || null,
          target_customers: targetCustomers.trim() || null,
          headquarters: headquarters.trim() || null,
          geography_scope: scope.trim() || null,
          notes: notes.trim() || null,
        },
      )
      onSaved(saved)
    } catch (exc) {
      setError(
        exc instanceof ApiError ? exc.message : 'Could not save those changes.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit {competitor.name}</DialogTitle>
          <DialogDescription>
            These are the fields you own. Everything the agent researched is
            read-only here on purpose &mdash; an edit cannot replace a cited
            finding with an uncited one.
          </DialogDescription>
        </DialogHeader>

        <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-name">Name</Label>
            <Input id="edit-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-website">Website</Label>
            <Input
              id="edit-website"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
            />
            <span className="text-[11px] text-muted-foreground">
              Changing this re-keys the company, so it stays the same tracked row
              rather than becoming a second one.
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit-target">Who they serve</Label>
              <Input
                id="edit-target"
                value={targetCustomers}
                onChange={(e) => setTargetCustomers(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edit-hq">Headquarters</Label>
              <Input
                id="edit-hq"
                value={headquarters}
                onChange={(e) => setHeadquarters(e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-scope">Where they operate</Label>
            <Input
              id="edit-scope"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder="local | regional | global"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-notes">Your note</Label>
            <Textarea
              id="edit-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Why they matter to you"
            />
            <span className="text-[11px] text-muted-foreground">
              Kept as your own words. A later search refreshes the research on
              this row and leaves this alone.
            </span>
          </div>
          {error && (
            <p className="flex items-start gap-1.5 text-[12px] leading-relaxed text-destructive">
              <AlertTriangle className="mt-0.5 size-3 shrink-0" />
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            className="cursor-pointer"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            type="button"
            className="cursor-pointer"
            onClick={() => void save()}
            disabled={busy}
          >
            {busy && <Loader2 className="size-3.5 animate-spin" />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Empty states
// ---------------------------------------------------------------------------

function EmptyWatchlist({ canRun }: { canRun: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-primary/20 bg-muted/30 px-6 py-12 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/15 text-amber-500">
        <Radar className="size-5" />
      </div>
      <p className="text-sm font-medium text-foreground">
        No competitors tracked yet
      </p>
      <p className="max-w-md text-xs leading-relaxed text-muted-foreground">
        {canRun
          ? 'Your discovery run mapped the competitive landscape as a profile of what a rival looks like here — the archetypes, pricing anchors and entry signals — without naming a single company. Search from that profile and every company it surfaces gets a real website, a cited profile, and a place on this list.'
          : 'Your discovery run has not produced a competitor profile yet, so there is nothing to search from. You can still add a competitor by URL — the agent will read that site and fill in the rest.'}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// The tab
// ---------------------------------------------------------------------------

export function CompetitionComponent({ workspaceId }: { workspaceId?: string }) {
  const { insights } = useInsights(workspaceId)
  const { competitors, setCompetitors, loading, error, refresh } =
    useCompetitors(workspaceId)

  const [tab, setTab] = useState<'tracked' | 'runs'>('tracked')
  const [addOpen, setAddOpen] = useState(false)
  const [editing, setEditing] = useState<Competitor | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)
  const [dismissedRunId, setDismissedRunId] = useState<string | null>(null)
  // Bumped after a run settles, to re-read the history the Runs tab shows.
  const [historyKey, setHistoryKey] = useState(0)

  const { track: trackManualResearch, pending: researchPending } =
    useManualResearchPolling(competitors, refresh)

  const {
    run,
    starting,
    start,
    startError,
    alreadyTracked,
    clearStartError,
  } = useLiveRun(
    workspaceId,
    () => {
      void refresh()
      setHistoryKey((k) => k + 1)
    },
  )
  const { runs, loading: runsLoading } = useRunHistory(workspaceId, historyKey)

  useEffect(() => {
    ensureInsightsLoaded(workspaceId)
  }, [workspaceId])

  const hasProfile = Boolean(insights?.ideal_competitor_profile?.archetypes?.length)

  const removeCompetitor = async (competitor: Competitor) => {
    if (!workspaceId) return
    setRemovingId(competitor.id)
    try {
      await deleteCompetitor(workspaceId, competitor.id)
      setCompetitors((prev) => prev.filter((c) => c.id !== competitor.id))
    } catch {
      // Leave the row in place: a failed delete that silently dropped it from
      // the screen would be worse than the error going unnoticed, since the
      // row is still on the server and comes back on the next load.
      void refresh()
    } finally {
      setRemovingId(null)
    }
  }

  const manualOnly = (competitors ?? []).filter((c) => c.source === 'manual').length

  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-0 flex-col">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-medium text-foreground">Competitors</h2>
          {(competitors ?? []).length > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[12px] font-medium tabular-nums text-muted-foreground">
              {(competitors ?? []).length} tracked
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="cursor-pointer"
            onClick={() => void start()}
            disabled={starting || (run !== null && LIVE_STATUSES.has(run.status))}
            title={
              hasProfile
                ? 'Search for companies matching your ideal competitor profile'
                : 'No competitor profile yet — this will search without one'
            }
          >
            {starting || (run !== null && LIVE_STATUSES.has(run.status)) ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Search className="size-3.5" />
            )}
            Find competitors
          </Button>
          <Button
            type="button"
            size="sm"
            className="cursor-pointer"
            onClick={() => setAddOpen(true)}
          >
            <Plus className="size-3.5" />
            Add by URL
          </Button>
        </div>
      </div>

      {startError && (
        <div className="mb-3 flex items-start justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-2.5">
          <p className="flex items-start gap-1.5 text-[12px] leading-relaxed text-destructive">
            <AlertTriangle className="mt-0.5 size-3 shrink-0" />
            {startError}
          </p>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="cursor-pointer text-destructive"
            onClick={clearStartError}
            aria-label="Dismiss"
          >
            <span aria-hidden>&times;</span>
          </Button>
        </div>
      )}

      {run && run.id !== dismissedRunId && (
        <div className="mb-3">
          <RunStatusStrip
            run={run}
            alreadyTracked={alreadyTracked}
            onDismiss={() => setDismissedRunId(run.id)}
          />
        </div>
      )}

      {error && (
        <p className="mb-3 rounded-lg border border-destructive/40 bg-destructive/5 p-2.5 text-[12px] text-destructive">
          {error}
        </p>
      )}

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as 'tracked' | 'runs')}
        className="flex min-h-0 flex-1 flex-col gap-3"
      >
        <TabsList variant="line" className="w-fit">
          <TabsTrigger value="tracked">Watch list</TabsTrigger>
          <TabsTrigger value="runs">
            <History className="size-3.5" />
            Runs
            {((Array.isArray(runs) ? runs.length : 0) > 0) && (
              <span className="ml-1 rounded-full bg-muted px-1.5 text-[11px] tabular-nums text-muted-foreground">
                {Array.isArray(runs) ? runs.length : 0}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="tracked" className="min-h-0 flex-1 overflow-y-auto pb-2">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-[13px] text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" />
              Loading your watch list
            </div>
          ) : (competitors ?? []).length === 0 ? (
            <EmptyWatchlist canRun={hasProfile} />
          ) : (
            <div className="flex flex-col gap-3">
              {competitors.map((competitor) => (
                <div
                  key={competitor.id}
                  className={cn(
                    'transition-opacity',
                    removingId === competitor.id && 'opacity-40',
                  )}
                >
                  <CompetitorCard
                    competitor={competitor}
                    busy={researchPending.has(competitor.id)}
                    onEdit={setEditing}
                    onRemove={(c) => void removeCompetitor(c)}
                  />
                </div>
              ))}
              {manualOnly > 0 && (
                <p className="px-1 pt-1 text-[11px] leading-relaxed text-muted-foreground/80">
                  {manualOnly} of these {manualOnly === 1 ? 'was' : 'were'} added
                  by you. Search runs refresh their research but leave your
                  notes and their place on the list alone.
                </p>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="runs" className="min-h-0 flex-1 overflow-y-auto pb-2">
          <RunHistory runs={runs} loading={runsLoading} />
        </TabsContent>
      </Tabs>

      {workspaceId && (
        <AddCompetitorDialog
          workspaceId={workspaceId}
          open={addOpen}
          onOpenChange={setAddOpen}
          onAdded={(competitor) => {
            // Read `competitors` from this render, which is the pre-add list, so
            // "was it already there" is answered before the refresh lands.
            const wasKnown = competitors.some((c) => c.id === competitor.id)
            void refresh()
            if (competitor.deep_researched_at === null) {
              trackManualResearch(competitor.id)
            }
            // The add endpoint is idempotent: 200 for a company already tracked,
            // 201 for a new one, and the row it returns is the same either way.
            // Rather than thread the status code through the fetch helper, this
            // is known exactly from the list a moment ago -- the id was either in
            // it or it was not.
            emitSignal({
              category: 'competitor',
              title: wasKnown
                ? `${competitor.name} is already tracked`
                : `Now tracking ${competitor.name}`,
              entity: competitor.name,
              summary: wasKnown
                ? `${competitor.website} was already on your watch list, so the list was left as it was. Its profile is being refreshed.`
                : `Added by URL. The agent is reading ${competitor.website} now and will fill in the rest of the profile from it.`,
              reason: wasKnown
                ? 'You added a competitor that was already on the watch list.'
                : 'You added this competitor by website URL.',
              sourceUrl: competitor.website,
              actions: [
                { kind: 'source', label: 'View source' },
                { kind: 'dismiss', label: 'Dismiss' },
              ],
            })
          }}
        />
      )}

      {workspaceId && editing && (
        <EditCompetitorDialog
          workspaceId={workspaceId}
          competitor={editing}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            setCompetitors((prev) =>
              prev.map((c) => (c.id === saved.id ? saved : c)),
            )
            setEditing(null)
          }}
        />
      )}
    </div>
  )
}

export default CompetitionComponent