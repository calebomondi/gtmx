import { useEffect, useMemo, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  ArrowRight,
  BellOff,
  Bot,
  ExternalLink,
  Flame,
  Inbox,
  Package,
  PenLine,
  Pin,
  PinOff,
  Search,
  Send,
  Star,
  Swords,
  Globe,
  X,
  Crosshair
} from 'lucide-react'
import { DotLottieReact } from '@lottiefiles/dotlottie-react'

import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useSession } from '@/lib/session-context'
import {
  ensureWorkspacesLoaded,
  useWorkspaces,
} from '@/lib/workspaces-store'
import { workspaceDisplayName } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { WorkspaceTab } from '@/lib/workspace-tab'

import { SignalDetailBody } from './signal-detail-body'

import { dismiss as dismissSignal, markRead, togglePin as toggleSignalPin, useSignals } from './feed-store'
import {
  formatTimeAgo,
  isRecent,
  type CategoryFilter,
  type RecencyFilter,
  type Signal,
  type SignalAction,
  type SignalCategory,
} from './feed-types'

const DAY_MS = 24 * 60 * 60 * 1000

export const CATEGORY_META: Record<SignalCategory, { label: string; icon: LucideIcon }> = {
  inbound: { label: 'Inbound', icon: Inbox },
  outbound: { label: 'Outbound', icon: Send },
  competitor: { label: 'Competitor', icon: Swords },
  market: { label: 'Market', icon: Globe },
  product: { label: 'Product', icon: Package },
  agent: { label: 'Agent', icon: Bot },
  opportunity: { label: 'Opportunity', icon: Crosshair },
}

const ACTION_META: Record<SignalAction['kind'], { icon: React.ReactNode; variant?: 'primary' }> = {
  reply: { icon: <PenLine className="size-4" />, variant: 'primary' },
  outreach: { icon: <ArrowRight className="size-4" /> },
  source: { icon: <ExternalLink className="size-4" /> },
  dismiss: { icon: <X className="size-4" /> },
  mute: { icon: <BellOff className="size-4" /> },
}

const CATEGORY_CHIPS: { value: CategoryFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'inbound', label: 'Inbound' },
  { value: 'outbound', label: 'Outbound' },
  { value: 'competitor', label: 'Competitor' },
  { value: 'market', label: 'Market' },
  { value: 'product', label: 'Product' },
  { value: 'agent', label: 'Agent' },
  { value: 'opportunity', label: 'Opportunity' },
]

export const RECENCY_CHIPS: { value: RecencyFilter; label: string }[] = [
  { value: '24hr', label: '24hr' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
  { value: '90d', label: '90d' },
]

const CATEGORY_ORDER: SignalCategory[] = [
  'inbound',
  'outbound',
  'competitor',
  'market',
  'product',
  'agent',
  'opportunity',
]

function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

function SignalCategoryIcon({
  category,
  className,
}: {
  category: SignalCategory
  className?: string
}) {
  const Icon = CATEGORY_META[category].icon
  return <Icon className={className} />
}

export function splitIntoSections<T extends Signal>(signals: T[]) {
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

  const byTime = (a: Signal, b: Signal) => b.timestamp - a.timestamp
  needsAttention.sort(byTime)
  today.sort(byTime)
  earlier.sort(byTime)

  return { needsAttention, today, earlier }
}

function SignalCard({
  signal,
  selected,
  onSelect,
  onTogglePin,
}: {
  signal: Signal
  selected: boolean
  onSelect: () => void
  onTogglePin: () => void
}) {
  const category = CATEGORY_META[signal.category]
  const Icon = category.icon

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect()
        }
      }}
      className={cn(
        'group flex w-full cursor-pointer items-start gap-3 rounded-lg border p-3 text-left transition-colors shadow-xs',
        selected
          ? 'border-amber-500/40 bg-muted/60'
          : 'border-transparent hover:border-primary/10 hover:bg-muted/40',
        signal.hot && !signal.read && 'border-amber-500/30',
      )}
    >
      <div
        className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
          selected ? 'bg-amber-500/15 text-amber-500' : 'bg-muted/70 text-muted-foreground',
        )}
      >
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
          <span className="truncate text-xs text-muted-foreground">
            {signal.summary}
          </span>
          {signal.hot && !signal.read && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-500">
              <Flame className="size-3" />
              hot
            </span>
          )}
        </div>
      </div>

      <Button
        type="button"
        size="icon-sm"
        variant="ghost"
        aria-label={signal.pinned ? 'Unpin' : 'Pin'}
        className={cn(
          'shrink-0 opacity-0 transition-opacity group-hover:opacity-100',
          signal.pinned && 'opacity-100 text-amber-500 hover:text-amber-500',
        )}
        onClick={(event) => {
          event.stopPropagation()
          onTogglePin()
        }}
      >
        {signal.pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
      </Button>
    </div>
  )
}

/** Where in the workspace each kind of item is worked on. */
const OPEN_IN: Partial<Record<Signal['category'], { tab: WorkspaceTab; label: string }>> = {
  product: { tab: 'product', label: 'Open the research' },
  competitor: { tab: 'competition', label: 'Open in Competitors' },
  opportunity: { tab: 'outreach', label: 'Open in Reach Out' },
}


function SignalDetail({
  signal,
  workspaceId,
  onTogglePin,
  onDismiss,
  onAction,
  onOpenTab,
}: {
  signal: Signal
  workspaceId: string | undefined
  onTogglePin: () => void
  onDismiss: () => void
  onAction: (action: SignalAction) => void
  onOpenTab?: (tab: WorkspaceTab) => void
}) {
  const category = CATEGORY_META[signal.category]
  const Icon = category.icon
  const openIn = onOpenTab ? OPEN_IN[signal.category] : undefined

  return (
    <>
      <DialogHeader className="border-b">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/15 text-amber-500">
            <Icon className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <DialogTitle className="truncate">{signal.title}</DialogTitle>
            <DialogDescription>
              {category.label} · {formatTimeAgo(signal.timestamp)}
            </DialogDescription>
          </div>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            aria-label={signal.pinned ? 'Unpin' : 'Pin'}
            className={cn(signal.pinned && 'text-amber-500 hover:text-amber-500')}
            onClick={onTogglePin}
          >
            {signal.pinned ? <PinOff className="size-4" /> : <Pin className="size-4" />}
          </Button>
        </div>
      </DialogHeader>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pb-4">
        {signal.sender && (
          <div className="flex items-center gap-3">
            <Avatar size="lg">
              <AvatarFallback>{initialsFor(signal.sender.name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{signal.sender.name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {signal.sender.email}
                {signal.sender.company ? ` · ${signal.sender.company}` : ''}
              </p>
            </div>
          </div>
        )}

        {signal.subject && (
          <p className="text-xs text-muted-foreground">
            <span className="text-foreground">re:</span> {signal.subject}
          </p>
        )}

        {signal.body && (
          <div className="overflow-hidden rounded-lg border bg-muted/40 p-3">
            <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
              {signal.body}
            </pre>
          </div>
        )}

        {signal.sourceUrl && (
          <a
            href={signal.sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-amber-500 hover:text-amber-400 hover:underline"
          >
            <ExternalLink className="size-3.5" />
            View source
          </a>
        )}

        <SignalDetailBody signal={signal} workspaceId={workspaceId} />

        <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-3">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-500">
            Why this matters
          </p>
          <p className="text-sm leading-relaxed text-muted-foreground">{signal.reason}</p>
        </div>
      </div>

      <DialogFooter className="border-t">
        <div className="flex flex-wrap items-center gap-2">
          {openIn && onOpenTab && (
            <Button
              type="button"
              className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950"
              onClick={() => onOpenTab(openIn.tab)}
            >
              {openIn.label}
            </Button>
          )}
          {signal.actions.map((action) => {
            const meta = ACTION_META[action.kind]
            return (
              <Button
                key={action.label}
                type="button"
                variant={meta.variant === 'primary' ? 'default' : 'outline'}
                className={cn(
                  'cursor-pointer',
                  meta.variant === 'primary' &&
                    'bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950',
                )}
                onClick={() => onAction(action)}
              >
                {meta.icon}
                {action.label}
              </Button>
            )
          })}
          <Button
            type="button"
            variant="ghost"
            className="ml-auto cursor-pointer text-muted-foreground"
            onClick={onDismiss}
          >
            <BellOff className="size-4" />
            Mute
          </Button>
        </div>
      </DialogFooter>
    </>
  )
}

export function SectionHeader({ label, count }: { label: string; count: number }) {
  if (count === 0) return null
  return (
    <div className="flex items-center gap-2 px-1 pt-4 pb-2 first:pt-2">
      <span className="text-[12px] font-semibold tracking-wide text-muted-foreground uppercase">
        {label}
      </span>
      <span className="rounded-full bg-muted/70 px-1.5 py-0.5 text-[11.5px] text-muted-foreground">
        {count}
      </span>
    </div>
  )
}

function EmptyFeed({ subject }: { subject: string }) {
  return (
    <div className="flex h-full min-h-64 flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="relative">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
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
          Agents are listening for signals on {subject}
        </p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Email replies, competitor moves, ICP intent, and agent work will land here as they're
          detected. Nothing yet — here's what will appear:
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {CATEGORY_ORDER.map((category) => (
          <span
            key={category}
            className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
          >
            <SignalCategoryIcon category={category} className="size-3.5" />
            {CATEGORY_META[category].label}
          </span>
        ))}
      </div>
    </div>
  )
}

export function FeedComponent({
  workspaceId,
  onOpenOutreach,
  onOpenTab,
}: {
  workspaceId?: string
  onOpenOutreach?: (contactEmail?: string) => void
  onOpenTab?: (tab: WorkspaceTab) => void
}) {
  const { product } = useSession()
  const { workspaces } = useWorkspaces()

  // The session snapshot only exists while a discovery run is fresh in memory,
  // so on any revisit it is null. Resolve the heading from the workspace itself
  // and fall back to the offer name only while the workspace is still loading.
  useEffect(() => {
    ensureWorkspacesLoaded()
  }, [])

  const workspace = workspaceId
    ? workspaces.find((item) => item.id === workspaceId)
    : undefined
  const subject =
    (workspace ? workspaceDisplayName(workspace) : null) ??
    product?.offer_name ??
    'your product/service'

  const signals = useSignals(workspaceId)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all')
  const [recency, setRecency] = useState<RecencyFilter>('90d')

  const unreadCount = useMemo(() => signals.filter((s) => !s.read).length, [signals])

  const filtered = useMemo(() => {
    const byCategory = categoryFilter === 'all' ? signals : signals.filter((s) => s.category === categoryFilter)
    return byCategory.filter((s) => isRecent(s, recency))
  }, [signals, categoryFilter, recency])

  const sections = useMemo(() => splitIntoSections(filtered), [filtered])

  const selected = signals.find((s) => s.id === selectedId) ?? null

  const openSignal = (id: string) => {
    const signal = signals.find((s) => s.id === id)
    markRead(id)
    // Contact-bearing signals (email/LinkedIn) open directly in OutReach, not a modal.
    if (signal?.sender?.email) {
      setSelectedId(null)
      setDetailOpen(false)
      onOpenOutreach?.(signal.sender.email)
      return
    }
    setSelectedId(id)
    setDetailOpen(true)
  }

  const togglePin = (id: string) => {
    toggleSignalPin(id)
  }

  const dismiss = (id: string) => {
    dismissSignal(id)
    setDetailOpen(false)
  }

  const handleAction = (action: SignalAction) => {
    if (!selected) return
    if (action.kind === 'dismiss') {
      dismiss(selected.id)
      return
    }
    // Reply/outreach deep-link into the OutReach tab for this contact.
    if (action.kind === 'reply' || action.kind === 'outreach') {
      setDetailOpen(false)
      onOpenOutreach?.(selected.sender?.email)
    }
  }

  const hasSignals = filtered.length > 0

  return (
    <div className="flex h-[calc(100dvh-var(--ws-chrome,7rem))] min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 mb-5">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-medium text-foreground">{subject} Feed</h2>
          {unreadCount > 0 && (
            <span className="flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-amber-500 px-1 text-xs font-medium text-amber-950">
              {unreadCount}
            </span>
          )}
        </div>
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
            <hr className="mb-3"/>
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
          <EmptyFeed subject={subject} />
        ) : (
          <div className="space-y-1">
            <SectionHeader label="Needs attention" count={sections.needsAttention.length} />
            {sections.needsAttention.map((signal) => (
              <SignalCard
                key={signal.id}
                signal={signal}
                selected={signal.id === selectedId}
                onSelect={() => openSignal(signal.id)}
                onTogglePin={() => togglePin(signal.id)}
              />
            ))}
            <SectionHeader label="Today" count={sections.today.length} />
            {sections.today.map((signal) => (
              <SignalCard
                key={signal.id}
                signal={signal}
                selected={signal.id === selectedId}
                onSelect={() => openSignal(signal.id)}
                onTogglePin={() => togglePin(signal.id)}
              />
            ))}
            <SectionHeader label="Earlier" count={sections.earlier.length} />
            {sections.earlier.map((signal) => (
              <SignalCard
                key={signal.id}
                signal={signal}
                selected={signal.id === selectedId}
                onSelect={() => openSignal(signal.id)}
                onTogglePin={() => togglePin(signal.id)}
              />
            ))}
            {filtered.length === 0 && (
              <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 text-center">
                <Search className="size-6 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  No signals in the last {recency} for this category.
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="cursor-pointer"
                  onClick={() => {
                    setCategoryFilter('all')
                    setRecency('90d')
                  }}
                >
                  <Star className="size-3.5" />
                  Show everything
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="sm:max-w-lg">
          {selected && (
            <SignalDetail
              signal={selected}
              workspaceId={workspaceId}
              onOpenTab={onOpenTab ? (tab) => { setDetailOpen(false); onOpenTab(tab) } : undefined}
              onTogglePin={() => togglePin(selected.id)}
              onDismiss={() => dismiss(selected.id)}
              onAction={handleAction}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default FeedComponent

// Re-exported for use outside the tab (e.g. tests, storyboards)
export { SignalCategoryIcon }