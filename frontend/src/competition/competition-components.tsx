import { useEffect, useRef, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  AtSign,
  Bot,
  Briefcase,
  ExternalLink,
  GitBranch,
  Globe,
  Link,
  Pencil,
  Plus,
  Radar,
  Sparkles,
  Trash2,
  X,
  CornerRightDown
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
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
import { Textarea } from '@/components/ui/textarea'
import { emitSignal } from '@/feed/feed-store'
import { useAgentRun } from '@/lib/agent-run-store'
import { ensureInsightsLoaded, useInsights } from '@/lib/insights-store'
import type { CompetitionDataDto } from '@/lib/api'

import {
  TRACKING_KIND_LABELS,
  TRACKING_KINDS,
  type CompetitionState,
  type Competitor,
  type PainSignal,
  type TrackingSource,
  type TrackingSourceKind,
} from './competition-types'

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] inline-flex font-medium tracking-wide text-foreground uppercase">
        <CornerRightDown className="h-3.5 w-3.5"/>
        {label}
      </span>
      <div className="text-sm leading-relaxed text-muted-foreground">{value}</div>
    </div>
  )
}

function TagPills({
  items,
  onRemove,
}: {
  items: string[]
  onRemove?: (item: string) => void
}) {
  if (items.length === 0) {
    return <span className="text-sm text-muted-foreground italic">—</span>
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="inline-flex items-center gap-1 rounded-full bg-muted/60 px-2 py-0.5 text-xs text-muted-foreground"
        >
          {item}
          {onRemove && (
            <button
              type="button"
              onClick={() => onRemove(item)}
              className="cursor-pointer text-muted-foreground hover:text-foreground"
              aria-label={`Remove ${item}`}
            >
              <X className="size-3" />
            </button>
          )}
        </span>
      ))}
    </div>
  )
}

function SectionCard({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <Card className="border-primary/15">
      <CardHeader className="flex flex-row items-start justify-between gap-2 border-b p-4 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-amber-500">
            {icon}
          </div>
          <div className="min-w-0">
            <CardTitle className="text-sm font-semibold">{title}</CardTitle>
            {description && (
              <CardDescription className="text-xs">{description}</CardDescription>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 p-4">
        {children}
      </CardContent>
    </Card>
  )
}

const TRACKING_ICONS: Record<TrackingSourceKind, LucideIcon> = {
  website: Globe,
  linkedin: Briefcase,
  x: AtSign,
  github: GitBranch,
  other: Link,
}

function isUrl(value: string): boolean {
  return /^https?:\/\//i.test(value)
}

function TrackingSources({ sources }: { sources: TrackingSource[] }) {
  const active = sources.filter((source) => source.value.trim() !== '')
  if (active.length === 0) {
    return <span className="text-sm text-muted-foreground italic">—</span>
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {active.map((source, index) => {
        const Icon = TRACKING_ICONS[source.kind]
        const content = (
          <>
            <Icon className="size-3" />
            <span className="max-w-40 truncate">{source.value}</span>
          </>
        )
        return isUrl(source.value) ? (
          <a
            key={`${source.kind}-${index}`}
            href={source.value}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-full bg-muted/60 px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted hover:text-amber-500"
          >
            {content}
          </a>
        ) : (
          <span
            key={`${source.kind}-${index}`}
            className="inline-flex items-center gap-1 rounded-full bg-muted/60 px-2 py-0.5 text-xs text-muted-foreground"
          >
            {content}
          </span>
        )
      })}
    </div>
  )
}

function TagEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string[]
  onChange: (next: string[]) => void
  placeholder?: string
}) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const trimmed = draft.trim()
    if (!trimmed) return
    onChange([...value, trimmed])
    setDraft('')
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex gap-1.5">
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              add()
            }
          }}
          placeholder={placeholder}
          className="h-8 flex-1 text-xs"
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0 cursor-pointer"
          onClick={add}
        >
          <Plus className="size-3.5" />
          Add
        </Button>
      </div>
      <TagPills
        items={value}
        onRemove={(item) => onChange(value.filter((v) => v !== item))}
      />
    </div>
  )
}

function TrackingSourceEditor({
  value,
  onChange,
}: {
  value: TrackingSource[]
  onChange: (next: TrackingSource[]) => void
}) {
  const patch = (index: number, field: keyof TrackingSource, val: string) =>
    onChange(
      value.map((source, i) => (i === index ? { ...source, [field]: val } : source)),
    )

  return (
    <div className="flex flex-col gap-2">
      {value.length === 0 && (
        <span className="text-xs text-muted-foreground italic">
          No sources tracked yet.
        </span>
      )}
      {value.map((source, index) => (
        <div key={index} className="flex items-center gap-1.5">
          <select
            value={source.kind}
            onChange={(event) =>
              patch(index, 'kind', event.target.value as TrackingSourceKind)
            }
            aria-label={`Source ${index + 1} type`}
            className="h-8 shrink-0 rounded-lg border border-primary/15 bg-muted/40 px-2 text-xs text-foreground"
          >
            {TRACKING_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {TRACKING_KIND_LABELS[kind]}
              </option>
            ))}
          </select>
          <Input
            value={source.value}
            onChange={(event) => patch(index, 'value', event.target.value)}
            placeholder={
              source.kind === 'website' ? 'https://…' : 'handle or profile URL'
            }
            className="h-8 flex-1 text-xs"
          />
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="shrink-0 cursor-pointer text-muted-foreground"
            onClick={() => onChange(value.filter((_, i) => i !== index))}
            aria-label="Remove source"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="w-fit cursor-pointer"
        onClick={() => onChange([...value, { kind: 'website', value: '' }])}
      >
        <Plus className="size-3.5" />
        Add source
      </Button>
    </div>
  )
}

function PainSignalsEditor({
  value,
  onChange,
}: {
  value: PainSignal[]
  onChange: (next: PainSignal[]) => void
}) {
  const patch = (index: number, field: keyof PainSignal, val: string | null) =>
    onChange(
      value.map((signal, i) => (i === index ? { ...signal, [field]: val } : signal)),
    )

  return (
    <div className="flex flex-col gap-2">
      {value.length === 0 && (
        <span className="text-xs text-muted-foreground italic">
          No pain signals captured.
        </span>
      )}
      {value.map((signal, index) => (
        <div
          key={index}
          className="flex flex-col gap-1.5 rounded-lg border border-primary/10 p-2"
        >
          <div className="flex items-start justify-between gap-2">
            <Textarea
              value={signal.pain}
              onChange={(event) => patch(index, 'pain', event.target.value)}
              placeholder="Pain point"
              className="h-14 min-h-0 text-xs"
            />
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              className="shrink-0 cursor-pointer text-muted-foreground"
              onClick={() => onChange(value.filter((_, i) => i !== index))}
              aria-label="Remove pain signal"
            >
              <X className="size-3.5" />
            </Button>
          </div>
          <Textarea
            value={signal.evidence}
            onChange={(event) => patch(index, 'evidence', event.target.value)}
            placeholder="What customers said — quote or paraphrase"
            className="h-12 min-h-0 text-xs"
          />
          <Input
            value={signal.source_url ?? ''}
            onChange={(event) =>
              patch(
                index,
                'source_url',
                event.target.value.trim() === '' ? null : event.target.value,
              )
            }
            placeholder="Source URL (optional)"
            className="h-8 text-xs"
          />
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="w-fit cursor-pointer"
        onClick={() =>
          onChange([...value, { pain: '', evidence: '', source_url: null }])
        }
      >
        <Plus className="size-3.5" />
        Add pain signal
      </Button>
    </div>
  )
}

function formatDeepResearchedAt(iso: string | null): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function initialOf(name: string): string {
  return (name.trim()[0] ?? '?').toUpperCase()
}

function CompetitorCard({
  competitor,
  onEdit,
  onRemove,
}: {
  competitor: Competitor
  onEdit: () => void
  onRemove: () => void
}) {
  const website =
    competitor.website ??
    competitor.tracking_sources.find((source) => source.kind === 'website')?.value
  const deepResearched = formatDeepResearchedAt(competitor.deep_researched_at)

  return (
    <Card className="border-primary/15">
      <CardHeader className="flex flex-row items-start justify-between gap-2 border-b p-4 pb-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-sm font-semibold text-amber-500">
            {initialOf(competitor.name)}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="truncate text-sm font-semibold">
                {competitor.name || 'Unnamed competitor'}
              </CardTitle>
            </div>
            {website && (
              <a
                href={website}
                target="_blank"
                rel="noreferrer"
                className="mt-0.5 inline-flex items-center text-blue-500 gap-1 text-xs hover:text-blue-600 hover:underline"
              >
                {website}
                <ExternalLink className="size-3" />
              </a>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="cursor-pointer text-muted-foreground"
            onClick={onEdit}
            aria-label={`Edit ${competitor.name}`}
          >
            <Pencil className="size-3.5" />
          </Button>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="cursor-pointer text-muted-foreground hover:text-rose-500"
            onClick={onRemove}
            aria-label={`Remove ${competitor.name}`}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 p-4">
        <Row label="Description" value={competitor.description || '—'} />

        <div className="flex flex-col gap-0.5">
          <span className="text-[11px] inline-flex font-medium tracking-wide text-foreground uppercase">
            <CornerRightDown className="h-3.5 w-3.5"/>
            Tracking sources
          </span>
          <TrackingSources sources={competitor.tracking_sources} />
          <span className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            Monitored by the agent — new signals push to Feed.
          </span>
        </div>

        {competitor.offering && (
          <Row label="Offering" value={competitor.offering} />
        )}
        {competitor.positioning && (
          <Row label="Positioning" value={competitor.positioning} />
        )}
        {competitor.comparison && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] inline-flex font-medium tracking-wide text-foreground uppercase">
              <CornerRightDown className="h-3.5 w-3.5"/>
              How we stack up
            </span>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {competitor.comparison}
            </p>
          </div>
        )}
        {competitor.business_model && (
          <Row label="Business model" value={competitor.business_model} />
        )}
        {competitor.pricing && <Row label="Pricing" value={competitor.pricing} />}
        {competitor.target_customers && (
          <Row label="Target customers" value={competitor.target_customers} />
        )}
        {competitor.notable_customers.length > 0 && (
          <Row
            label="Notable customers"
            value={<TagPills items={competitor.notable_customers} />}
          />
        )}
        {competitor.strengths.length > 0 && (
          <Row label="Strengths" value={<TagPills items={competitor.strengths} />} />
        )}
        {competitor.weaknesses.length > 0 && (
          <Row
            label="Weaknesses"
            value={<TagPills items={competitor.weaknesses} />}
          />
        )}
        {competitor.whats_unique && (
          <Row label="What's unique" value={competitor.whats_unique} />
        )}
        {competitor.pain_signals.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] inline-flex font-medium tracking-wide text-foreground uppercase">
              <CornerRightDown className="h-3.5 w-3.5"/>
              Customer pain signals
            </span>
            <div className="flex flex-col gap-1.5">
              {competitor.pain_signals.map((signal, index) => (
                <div
                  key={index}
                  className="rounded-lg border border-primary/10 p-2"
                >
                  <p className="text-sm font-medium text-foreground">
                    {signal.pain}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {signal.evidence}
                  </p>
                  {signal.source_url && (
                    <a
                      href={signal.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-0.5 inline-flex items-center gap-1 text-xs text-amber-500 hover:text-amber-400 hover:underline"
                    >
                      source
                      <ExternalLink className="size-3" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center gap-2 border-t border-primary/10 pt-2">
          {deepResearched ? (
            <>
              <Sparkles className="size-3.5 text-amber-500" />
              <span className="text-xs text-muted-foreground">
                Deep-dived by agent · {deepResearched}
              </span>
            </>
          ) : (
            <span className="text-xs text-muted-foreground italic">
              Awaiting first deep-dive
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function normalizeCompetitor(competitor: Competitor): Competitor {
  const tracking_sources = competitor.tracking_sources
    .map((source) => ({ ...source, value: source.value.trim() }))
    .filter((source) => source.value !== '')
  const website =
    competitor.website?.trim() ||
    tracking_sources.find((source) => source.kind === 'website')?.value ||
    null
  return { ...competitor, tracking_sources, website }
}

function AddCompetitorDialog({
  open,
  onOpenChange,
  onAdd,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (competitor: Competitor) => void
}) {
  const [draft, setDraft] = useState<Competitor>(() => emptyCompetitor())

  useEffect(() => {
    if (open) setDraft(emptyCompetitor())
  }, [open])

  const patch = <K extends keyof Competitor>(key: K, val: Competitor[K]) =>
    setDraft((prev) => ({ ...prev, [key]: val }))

  const name = draft.name.trim()
  const hasSource = draft.tracking_sources.some(
    (source) => source.value.trim() !== '',
  )
  const canSave = name.length > 0 && hasSource

  const save = () => {
    if (!canSave) return
    onAdd(normalizeCompetitor(draft))
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="border-b">
          <DialogTitle className="text-base">Track a competitor</DialogTitle>
          <DialogDescription>
            Add a competitor. The agent will monitor the sources below and push
            new signals to your Feed.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Competitor name</Label>
            <Input
              value={draft.name}
              onChange={(event) => patch('name', event.target.value)}
              placeholder="e.g. HeatherDB"
              className="h-8 text-xs"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Description</Label>
            <Textarea
              value={draft.description}
              onChange={(event) => patch('description', event.target.value)}
              placeholder="What this competitor does (optional)"
              className="h-16 min-h-0 text-xs"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">
              Website or social media handles
            </Label>
            <TrackingSourceEditor
              value={draft.tracking_sources}
              onChange={(sources) => patch('tracking_sources', sources)}
            />
          </div>
        </div>
        <DialogFooter className="border-t">
          <Button
            type="button"
            variant="ghost"
            className="cursor-pointer"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            className="cursor-pointer"
            disabled={!canSave}
            onClick={save}
          >
            <Plus className="size-4" />
            Track competitor
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function emptyCompetitor(): Competitor {
  return {
    name: '',
    description: '',
    website: null,
    tracking_sources: [{ kind: 'website', value: '' }],
    offering: null,
    positioning: null,
    comparison: null,
    business_model: null,
    pricing: null,
    target_customers: null,
    notable_customers: [],
    strengths: [],
    weaknesses: [],
    whats_unique: null,
    pain_signals: [],
    deep_researched_at: null,
  }
}

function EditCompetitorDialog({
  open,
  onOpenChange,
  initial,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initial: Competitor
  onSave: (competitor: Competitor) => void
}) {
  const [draft, setDraft] = useState<Competitor>(() => clone(initial))

  useEffect(() => {
    if (open) setDraft(clone(initial))
  }, [open, initial])

  const patch = <K extends keyof Competitor>(key: K, val: Competitor[K]) =>
    setDraft((prev) => ({ ...prev, [key]: val }))

  const canSave = draft.name.trim().length > 0

  const save = () => {
    if (!canSave) return
    onSave(normalizeCompetitor(draft))
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="border-b">
          <DialogTitle className="text-base">Edit competitor</DialogTitle>
          <DialogDescription>
            Update the tracked sources and research profile for this competitor.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Competitor name</Label>
            <Input
              value={draft.name}
              onChange={(event) => patch('name', event.target.value)}
              placeholder="e.g. HeatherDB"
              className="h-8 text-xs"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Description</Label>
            <Textarea
              value={draft.description}
              onChange={(event) => patch('description', event.target.value)}
              placeholder="What this competitor does"
              className="h-14 min-h-0 text-xs"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">
              Website or social media handles
            </Label>
            <TrackingSourceEditor
              value={draft.tracking_sources}
              onChange={(sources) => patch('tracking_sources', sources)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Offering</Label>
            <Textarea
              value={draft.offering ?? ''}
              onChange={(event) => patch('offering', event.target.value || null)}
              placeholder="Key features and services they offer"
              className="h-14 min-h-0 text-xs"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Positioning</Label>
            <Textarea
              value={draft.positioning ?? ''}
              onChange={(event) =>
                patch('positioning', event.target.value || null)
              }
              placeholder="How they position themselves in the market"
              className="h-14 min-h-0 text-xs"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">How we stack up</Label>
            <Textarea
              value={draft.comparison ?? ''}
              onChange={(event) => patch('comparison', event.target.value || null)}
              placeholder="Advantages and gaps vs our product"
              className="h-14 min-h-0 text-xs"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-medium">Business model</Label>
              <Input
                value={draft.business_model ?? ''}
                onChange={(event) =>
                  patch('business_model', event.target.value || null)
                }
                placeholder="e.g. Seat-based SaaS"
                className="h-8 text-xs"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-medium">Pricing</Label>
              <Input
                value={draft.pricing ?? ''}
                onChange={(event) => patch('pricing', event.target.value || null)}
                placeholder="Pricing model and price points"
                className="h-8 text-xs"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-medium">Target customers</Label>
              <Input
                value={draft.target_customers ?? ''}
                onChange={(event) =>
                  patch('target_customers', event.target.value || null)
                }
                placeholder="Who they sell to"
                className="h-8 text-xs"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-medium">What's unique</Label>
              <Input
                value={draft.whats_unique ?? ''}
                onChange={(event) =>
                  patch('whats_unique', event.target.value || null)
                }
                placeholder="What's genuinely unique"
                className="h-8 text-xs"
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Notable customers</Label>
            <TagEditor
              value={draft.notable_customers}
              onChange={(items) => patch('notable_customers', items)}
              placeholder="Add a known customer"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-medium">Strengths</Label>
              <TagEditor
                value={draft.strengths}
                onChange={(items) => patch('strengths', items)}
                placeholder="Add a strength"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-medium">Weaknesses</Label>
              <TagEditor
                value={draft.weaknesses}
                onChange={(items) => patch('weaknesses', items)}
                placeholder="Add a weakness"
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Customer pain signals</Label>
            <PainSignalsEditor
              value={draft.pain_signals}
              onChange={(signals) => patch('pain_signals', signals)}
            />
          </div>
        </div>
        <DialogFooter className="border-t">
          <Button
            type="button"
            variant="ghost"
            className="cursor-pointer"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            className="cursor-pointer"
            disabled={!canSave}
            onClick={save}
          >
            Save changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function EmptyCompetition() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-primary/20 bg-muted/30 px-6 py-10 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/15 text-amber-500">
        <Radar className="size-5" />
      </div>
      <p className="text-sm font-medium text-foreground">
        No competitors tracked yet
      </p>
      <p className="max-w-xs text-xs text-muted-foreground">
        Add a competitor with a website or social handle and the agent will
        start monitoring it and surface new intel in your Feed.
      </p>
    </div>
  )
}

const EMPTY_COMPETITION_STATE: CompetitionState = {
  competitors: [],
  strengths: [],
  weaknesses: [],
  opportunities: [],
  differentiators: [],
}

function competitionStateFromDto(dto: CompetitionDataDto): CompetitionState {
  return {
    competitors: dto.competitors.map((competitor) => ({
      name: competitor.name,
      description: competitor.description,
      website: competitor.website ?? null,
      tracking_sources: competitor.website
        ? [{ kind: 'website' as const, value: competitor.website }]
        : [],
      offering: competitor.offering ?? null,
      positioning: competitor.positioning ?? null,
      comparison: competitor.comparison ?? null,
      business_model: null,
      pricing: null,
      target_customers: null,
      notable_customers: [],
      strengths: [],
      weaknesses: [],
      whats_unique: null,
      pain_signals: [],
      deep_researched_at: null,
    })),
    strengths: dto.strengths,
    weaknesses: dto.weaknesses,
    opportunities: dto.opportunities,
    differentiators: dto.differentiators,
  }
}

export function CompetitionComponent({ workspaceId }: { workspaceId?: string }) {
  const { insights } = useInsights(workspaceId)
  const run = useAgentRun()
  const [state, setState] = useState<CompetitionState>(EMPTY_COMPETITION_STATE)
  // Once the user edits the list locally, fetched data no longer overwrites it.
  const editedRef = useRef(false)
  const [addOpen, setAddOpen] = useState(false)
  const [editIndex, setEditIndex] = useState<number | null>(null)

  const runBelongsToWorkspace =
    workspaceId !== undefined && run.workspaceId === workspaceId
  const competitionData =
    (runBelongsToWorkspace
      ? run.phaseResults.understand_competition
      : undefined) ??
    insights?.competition_data ??
    null

  useEffect(() => {
    ensureInsightsLoaded(workspaceId)
  }, [workspaceId])

  useEffect(() => {
    if (editedRef.current) return
    setState(
      competitionData
        ? competitionStateFromDto(competitionData)
        : EMPTY_COMPETITION_STATE,
    )
  }, [competitionData])

  const removeCompetitor = (index: number) => {
    editedRef.current = true
    setState((prev) => ({
      ...prev,
      competitors: prev.competitors.filter((_, i) => i !== index),
    }))
  }

  const handleAdd = (competitor: Competitor) => {
    editedRef.current = true
    setState((prev) => ({
      ...prev,
      competitors: [competitor, ...prev.competitors],
    }))
    const sourceSummary =
      competitor.tracking_sources.map((source) => source.value).join(', ') ||
      competitor.website ||
      'their web presence'
    emitSignal({
      category: 'competitor',
      title: `Now tracking ${competitor.name}`,
      entity: competitor.name,
      summary: `${competitor.name} was added to the tracking list. The agent is monitoring ${sourceSummary} and will push new signals here as they surface.`,
      reason:
        'New competitor added by you. The agent will research the tracked sites and handles, then surface positioning, pricing, and threat signals.',
      sourceUrl: competitor.website ?? undefined,
      actions: [
        { kind: 'source', label: 'View source' },
        { kind: 'dismiss', label: 'Dismiss' },
      ],
    })
  }

  const handleSave = (index: number, competitor: Competitor) => {
    editedRef.current = true
    setState((prev) => ({
      ...prev,
      competitors: prev.competitors.map((existing, i) =>
        i === index ? competitor : existing,
      ),
    }))
  }

  const editing =
    editIndex !== null ? (state.competitors[editIndex] ?? null) : null

  const hasAnyContent =
    state.competitors.length > 0 ||
    state.strengths.length > 0 ||
    state.weaknesses.length > 0 ||
    state.opportunities.length > 0 ||
    state.differentiators.length > 0

  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 mb-5">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-medium text-foreground">Competition</h2>
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[12px] font-medium text-amber-500">
            <Bot className="size-4.5" />
            agent tracking
          </span>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="cursor-pointer"
          onClick={() => setAddOpen(true)}
        >
          <Plus className="size-3.5" />
          Add competitor
        </Button>
      </div>

      <hr className="mb-3"/>

      <div className="mt-3 min-h-0 flex-1 overflow-y-auto pb-2">
        {!hasAnyContent ? (
          <EmptyCompetition />
        ) : (
        <div className="flex flex-col gap-3">
          <SectionCard
            icon={<Bot className="size-4.5" />}
            title="Agent read"
            description="Competitive summary produced by the competition specialist"
          >
            <Row label="Strengths" value={<TagPills items={state.strengths} />} />
            <Row
              label="Weaknesses"
              value={<TagPills items={state.weaknesses} />}
            />
            <Row
              label="Opportunities"
              value={<TagPills items={state.opportunities} />}
            />
            <Row
              label="Differentiators"
              value={<TagPills items={state.differentiators} />}
            />
          </SectionCard>

          <SectionCard
            icon={<Radar className="size-4" />}
            title="Tracked competitors"
            description={`${state.competitors.length} on watch — new signals push to Feed`}
          >
            {state.competitors.length === 0 ? (
              <EmptyCompetition />
            ) : (
              <div className="flex flex-col gap-3">
                {state.competitors.map((competitor, index) => (
                  <CompetitorCard
                    key={`${competitor.name}-${index}`}
                    competitor={competitor}
                    onEdit={() => setEditIndex(index)}
                    onRemove={() => removeCompetitor(index)}
                  />
                ))}
              </div>
            )}
          </SectionCard>
        </div>
        )}
      </div>

      <AddCompetitorDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onAdd={handleAdd}
      />

      {editing && (
        <EditCompetitorDialog
          open={true}
          onOpenChange={(open) => {
            if (!open) setEditIndex(null)
          }}
          initial={editing}
          onSave={(competitor) => {
            if (editIndex === null) return
            handleSave(editIndex, competitor)
            setEditIndex(null)
          }}
        />
      )}
    </div>
  )
}

export default CompetitionComponent