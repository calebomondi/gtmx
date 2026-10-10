import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Flame, Pin, PinOff, RefreshCcw, X } from 'lucide-react'
import { DotLottieReact } from '@lottiefiles/dotlottie-react'

import { Button } from '@/components/ui/button'
import { ensureWorkspacesLoaded, refetchWorkspaces, useWorkspaces } from '@/lib/workspaces-store'
import { ensureProjectsLoaded, useProjects } from '@/lib/projects-store'
import { cn } from '@/lib/utils'

import {
  CATEGORY_META,
  RECENCY_CHIPS,
  SectionHeader,
} from '@/features/feed/feed-components'
import { formatTimeAgo, isRecent, type RecencyFilter, type Signal } from '@/features/feed/feed-types'

import { dismiss as dismissSignal, markRead, togglePin as toggleSignalPin, useSignals } from '@/features/feed/feed-store'
import {
  CATEGORY_TARGET_TAB,
  type HomeCategory,
  type HomeCategoryFilter,
  type HomeSignal,
} from './home-feed-types'

const CATEGORY_CHIPS: { value: HomeCategoryFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'inbound', label: 'Inbound' },
  { value: 'outbound', label: 'Outbound' },
  { value: 'competitor', label: 'Competitor' },
  { value: 'product', label: 'Product' },
  { value: 'agent', label: 'Agent' },
  { value: 'opportunity', label: 'Opportunity' },
]

const HOME_CATEGORIES: HomeCategory[] = [
  'inbound',
  'outbound',
  'competitor',
  'product',
  'agent',
  'opportunity',
]

function targetTabFor(signal: HomeSignal) {
  return signal.category in CATEGORY_TARGET_TAB
    ? CATEGORY_TARGET_TAB[signal.category as keyof typeof CATEGORY_TARGET_TAB]
    : 'feed'
}

const DAY_MS = 86_400_000

/**
 * Same buckets as the workspace feed, but order is preserved so the caller can
 * apply its own priority ordering (project priority → pinned → recency).
 */
function splitIntoSectionsOrdered<T extends Signal>(signals: T[]) {
  const needsAttention: T[] = []
  const today: T[] = []
  const earlier: T[] = []

  for (const signal of signals) {
    if (signal.hot && !signal.read) {
      needsAttention.push(signal)
    } else if (Date.now() - signal.timestamp < DAY_MS) {
      today.push(signal)
    } else {
      earlier.push(signal)
    }
  }

  return { needsAttention, today, earlier }
}

function HomeSignalCard({
  signal,
  onOpen,
  onTogglePin,
  onDismiss,
}: {
  signal: HomeSignal
  onOpen: () => void
  onTogglePin: () => void
  onDismiss: () => void
}) {
  const category = CATEGORY_META[signal.category]
  const Icon = category.icon

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen()
        }
      }}
      className={cn(
        'group flex w-full cursor-pointer items-start gap-3 rounded-lg border p-3 text-left transition-colors shadow-xs',
        signal.hot && !signal.read
          ? 'border-amber-500/30 hover:border-amber-500/40 hover:bg-muted/40'
          : 'border-transparent hover:border-primary/10 hover:bg-muted/40',
      )}
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/70 text-muted-foreground transition-colors group-hover:bg-amber-500/15 group-hover:text-amber-500">
        <Icon className="size-4" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {!signal.read && (
            <span
              className={cn(
                'size-1.5 shrink-0 rounded-full',
                signal.hot ? 'bg-amber-500' : 'bg-sky-500',
              )}
            />
          )}
          <span className="truncate text-sm font-medium text-foreground">{signal.title}</span>
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {formatTimeAgo(signal.timestamp)}
          </span>
        </div>

        <div className="mt-1 flex min-w-0 items-center gap-2">
          <span className="truncate text-xs text-muted-foreground">{signal.summary}</span>
          {signal.hot && !signal.read && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-500">
              <Flame className="size-3" />
              hot
            </span>
          )}
        </div>

        <div className="mt-2 flex items-center gap-2">
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-primary/10 bg-muted/60 px-1.5 py-0.5 text-[11px] font-medium text-foreground">
            <span aria-hidden className="size-2 rounded-[2px] bg-[#FEA853]" />
            {signal.workspace.name}
          </span>
          <span className="ml-auto inline-flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            Open in {signal.workspace.name}
            <ArrowRight className="size-3" />
          </span>
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-center gap-0.5">
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          aria-label={signal.pinned ? 'Unpin' : 'Pin'}
          className={cn(
            'opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100',
            signal.pinned && 'opacity-100 text-amber-500 hover:text-amber-500',
          )}
          onClick={(event) => {
            event.stopPropagation()
            onTogglePin()
          }}
        >
          {signal.pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
        </Button>
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          aria-label="Dismiss"
          className="opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
          onClick={(event) => {
            event.stopPropagation()
            onDismiss()
          }}
        >
          <X className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}

function EmptyHomeFeed({ workspaceCount }: { workspaceCount: number }) {
  const navigate = useNavigate()

  if (workspaceCount === 0) {
    return (
      <div className="flex h-full min-h-64 flex-col items-center justify-center gap-4 px-6 text-center">
        <div className="flex h-18 w-18 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
          <DotLottieReact
            src="/empty.lottie"
            loop
            autoplay
            onError={() => {}}
            className="w-full h-auto"
          />
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">No workspaces yet</p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Create your first workspace and the agent will start watching email replies,
            competitor moves, and agent work — everything will land here.
          </p>
        </div>
        <Button
          type="button"
          size="lg"
          className="cursor-pointer rounded-lg bg-[#FEA853]"
          onClick={() => navigate('/new')}
        >
          Create a workspace
          <ArrowRight className="size-3.5" />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-64 flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="relative">
        <div className="flex h-18 w-18 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
          <DotLottieReact
            src="/empty.lottie"
            loop
            autoplay
            onError={() => {}}
            className="w-full h-auto"
          />
        </div>
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">
          Agents are listening across {workspaceCount} workspaces
        </p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Email replies, competitor moves, and agent work from every workspace will land here as
          they're detected. Nothing yet — here's what will appear:
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {HOME_CATEGORIES.map((category) => (
          <span
            key={category}
            className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
          >
            {(() => {
              const Icon = CATEGORY_META[category].icon
              return <Icon className="size-3.5" />
            })()}
            {CATEGORY_META[category].label}
          </span>
        ))}
      </div>
    </div>
  )
}

export function HomeFeed() {
  const navigate = useNavigate()
  const signals = useSignals()
  const { workspaces } = useWorkspaces()
  const { projects } = useProjects()
  const [categoryFilter, setCategoryFilter] = useState<HomeCategoryFilter>('all')
  const [recency, setRecency] = useState<RecencyFilter>('90d')
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    ensureWorkspacesLoaded()
    ensureProjectsLoaded()
  }, [])

  const workspaceCount = workspaces.length
  const unreadCount = useMemo(() => signals.filter((s) => !s.read).length, [signals])

  // Workspaces in a priority project rank above everything else.
  const workspaceRank = useMemo(() => {
    const priorityProjects = new Set(
      projects.filter((project) => project.priority).map((project) => project.id),
    )
    const rank = new Map<string, number>()
    for (const workspace of workspaces) {
      const inPriorityProject =
        workspace.project_id !== null && priorityProjects.has(workspace.project_id)
      rank.set(workspace.id, inPriorityProject ? 0 : 1)
    }
    return rank
  }, [workspaces, projects])

  const filtered = useMemo(() => {
    const byCategory =
      categoryFilter === 'all' ? signals : signals.filter((s) => s.category === categoryFilter)
    return byCategory
      .filter((s) => isRecent(s, recency))
      .slice()
      .sort((a, b) => {
        const rank =
          (workspaceRank.get(a.workspace.id) ?? 1) - (workspaceRank.get(b.workspace.id) ?? 1)
        if (rank !== 0) return rank
        if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
        return b.timestamp - a.timestamp
      })
  }, [signals, categoryFilter, recency, workspaceRank])

  const sections = useMemo(() => splitIntoSectionsOrdered(filtered), [filtered])

  const openSignal = (signal: HomeSignal) => {
    markRead(signal.id)
    navigate(`/workspace/${signal.workspace.id}?tab=${targetTabFor(signal)}`)
  }

  const togglePin = (id: string) => {
    toggleSignalPin(id)
  }

  const dismiss = (id: string) => {
    dismissSignal(id)
  }

  const runScan = async () => {
    setScanning(true)
    try {
      await refetchWorkspaces()
    } finally {
      setScanning(false)
    }
  }

  const hasSignals = filtered.length > 0

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-muted p-6 md:p-10">
      <div className="mx-auto flex w-full min-h-0 max-w-3xl flex-1 flex-col">
        <div className="mb-5 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h1 className="font-medium text-xl">Home Feed</h1>
            {
              workspaceCount > 0 && (
                <span className="hidden text-sm text-muted-foreground sm:inline">
                  across {workspaceCount} workspace{workspaceCount === 1 ? '' : 's'}
                </span>
              )
            }
            {unreadCount > 0 && (
              <span className="flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-amber-500 px-1 text-xs font-medium text-amber-950">
                {unreadCount}
              </span>
            )}
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="cursor-pointer rounded-full h-3.5 w-3.5 p-3.5"
            onClick={runScan}
            aria-label="Scan for new signals"
          >
            <RefreshCcw className={cn('size-3.5', scanning && 'animate-spin')} />
          </Button>
        </div>

        <div className="mt-3 flex flex-col gap-2">
          {signals.length > 0 && (
            <>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {CATEGORY_CHIPS.map((chip) => (
                  <button
                    key={chip.value}
                    type="button"
                    onClick={() => setCategoryFilter(chip.value)}
                    className={cn(
                      'cursor-pointer rounded-full border px-2.5 py-1.5 text-xs font-medium transition-colors',
                      categoryFilter === chip.value
                        ? 'border-amber-500 bg-amber-500 text-amber-950'
                        : 'border-border bg-secondary text-secondary-foreground hover:bg-accent hover:text-accent-foreground',
                    )}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
              <hr className="mb-3" />
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] tracking-wide text-muted-foreground uppercase">Past</span>
                {RECENCY_CHIPS.map((chip) => (
                  <button
                    key={chip.value}
                    type="button"
                    onClick={() => setRecency(chip.value)}
                    className={cn(
                      'cursor-pointer rounded-md px-2 py-0.5 text-xs font-medium transition-colors',
                      recency === chip.value
                        ? 'bg-muted text-foreground'
                        : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                    )}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="mt-3 min-h-0 flex-1 overflow-y-auto pb-2">
          {!hasSignals ? (
            <EmptyHomeFeed workspaceCount={workspaceCount} />
          ) : (
            <div className="space-y-1">
              <SectionHeader label="Needs attention" count={sections.needsAttention.length} />
              {sections.needsAttention.map((signal) => (
                <HomeSignalCard
                  key={signal.id}
                  signal={signal}
                  onOpen={() => openSignal(signal)}
                  onTogglePin={() => togglePin(signal.id)}
                  onDismiss={() => dismiss(signal.id)}
                />
              ))}
              <SectionHeader label="Today" count={sections.today.length} />
              {sections.today.map((signal) => (
                <HomeSignalCard
                  key={signal.id}
                  signal={signal}
                  onOpen={() => openSignal(signal)}
                  onTogglePin={() => togglePin(signal.id)}
                  onDismiss={() => dismiss(signal.id)}
                />
              ))}
              <SectionHeader label="Earlier" count={sections.earlier.length} />
              {sections.earlier.map((signal) => (
                <HomeSignalCard
                  key={signal.id}
                  signal={signal}
                  onOpen={() => openSignal(signal)}
                  onTogglePin={() => togglePin(signal.id)}
                  onDismiss={() => dismiss(signal.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default HomeFeed
