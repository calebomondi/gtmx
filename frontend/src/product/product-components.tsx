import { useEffect, useRef, useState } from 'react'
import { Row, SectionCard, TagPills } from './product-sections'
import { CompetitionPanel, OfferTabNav, type OfferTab } from './offer-tabs'

import {
  Bot,
  ExternalLink,
  Package,
  Pencil,
  Plus,
  CornerRightDown,
  CornerDownRight,
  Globe,
  UserRoundCheck,
  X,
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
import { Tabs, TabsContent } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useSession } from '@/lib/session-context'
import { useAgentRun, type PhaseResults } from '@/lib/agent-run-store'
import { ensureInsightsLoaded, useInsights } from '@/lib/insights-store'
import type { IcpDto, MarketDataDto, OfferSnapshot, WorkspaceInsights } from '@/lib/api'
import { cn } from '@/lib/utils'

import {
  BUYER_TYPES,
  FIT_VERDICTS,
  PRODUCT_CATEGORIES,
  type CompetitorLead,
  type ICP,
  type MarketExtraction,
  type MarketFitVerdict,
  type Pricing,
  type ProductCategory,
  type BuyerType,
  type PricingSource,
  type ProductState,
  type SnapshotFeature,
} from './product-types'

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

const VERDICT_STYLES: Record<MarketFitVerdict, string> = {
  strong: 'bg-emerald-500/15 text-emerald-500',
  moderate: 'bg-amber-500/15 text-amber-500',
  weak: 'bg-rose-500/15 text-rose-500',
  unclear: 'bg-muted text-muted-foreground',
}

function VerdictBadge({ verdict }: { verdict: MarketFitVerdict }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase',
        VERDICT_STYLES[verdict],
      )}
    >
      {verdict}
    </span>
  )
}

function AgentInsight({
  label,
  value,
  onEdit,
}: {
  label: string
  value: string | null
  onEdit: () => void
}) {
  return (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-3">
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-medium tracking-wide text-amber-500 uppercase">
          <CornerDownRight className="size-3.5" />
          {label}
        </p>
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          aria-label={`Edit ${label}`}
          className="cursor-pointer text-muted-foreground hover:text-foreground"
          onClick={onEdit}
        >
          <Pencil className="size-3.5" />
        </Button>
      </div>
      <p className="text-sm leading-relaxed text-muted-foreground">
        {value || 'Not captured yet.'}
      </p>
    </div>
  )
}

function EmptyProduct({ productName }: { productName: string }) {
  return (
    <div className="flex h-full min-h-64 flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
        <Package className="size-5" />
      </div>
      <p className="text-sm font-medium text-foreground">
        No product/service profile yet for {productName}
      </p>
      <p className="text-sm leading-relaxed text-muted-foreground">
        Run the discovery flow to capture the product/service snapshot, domain and market-fit
        understanding, market data, and ICP.
      </p>
    </div>
  )
}

function TagEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string[]
  onChange: (value: string[]) => void
  placeholder?: string
}) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const tag = draft.trim()
    if (!tag) return
    if (!value.includes(tag)) onChange([...value, tag])
    setDraft('')
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        {value.length === 0 && (
          <span className="text-xs text-muted-foreground italic">None</span>
        )}
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-muted/60 px-2 py-0.5 text-xs text-muted-foreground"
          >
            {tag}
            <button
              type="button"
              aria-label={`Remove ${tag}`}
              className="cursor-pointer text-muted-foreground hover:text-foreground"
              onClick={() => onChange(value.filter((item) => item !== tag))}
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
      </div>
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
          placeholder={placeholder ?? 'Add…'}
          className="h-8 bg-background text-xs"
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0 cursor-pointer"
          onClick={add}
          aria-label="Add tag"
        >
          <Plus className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}

function ChoiceChips<T extends string>({
  options,
  value,
  onChange,
  unsetLabel,
}: {
  options: T[]
  value: T | null
  onChange: (value: T | null) => void
  unsetLabel?: string
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(value === option ? null : option)}
          className={cn(
            'cursor-pointer rounded-full px-2.5 py-1 text-xs font-medium transition-colors',
            value === option
              ? 'bg-amber-500 text-amber-950'
              : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
        >
          {option}
        </button>
      ))}
      {unsetLabel && value === null && (
        <span className="text-xs text-muted-foreground italic">{unsetLabel}</span>
      )}
    </div>
  )
}

function EditTextDialog({
  open,
  onOpenChange,
  title,
  description,
  value,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  value: string
  onSave: (value: string) => void
}) {
  const [draft, setDraft] = useState(value)

  useEffect(() => {
    if (open) setDraft(value)
  }, [open, value])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="border-b">
          <DialogTitle className="text-base">{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Write the agent understanding…"
            className="min-h-32 resize-none"
          />
        </div>
        <DialogFooter className="border-t">
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="cursor-pointer"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950"
              disabled={!draft.trim()}
              onClick={() => {
                onSave(draft.trim())
                onOpenChange(false)
              }}
            >
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

type SnapshotDraft = OfferSnapshot

function EditSnapshotDialog({
  open,
  onOpenChange,
  value,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  value: SnapshotDraft
  onSave: (value: SnapshotDraft) => void
}) {
  const [draft, setDraft] = useState<SnapshotDraft>(() => clone(value))

  useEffect(() => {
    if (open) setDraft(clone(value))
  }, [open, value])

  const patch = <K extends keyof SnapshotDraft>(
    key: K,
    val: SnapshotDraft[K],
  ) => setDraft((prev) => ({ ...prev, [key]: val }))

  const patchFeature = (index: number, key: keyof SnapshotFeature, val: string) =>
    patch(
      'features',
      draft.features.map((feature, i) =>
        i === index ? { ...feature, [key]: val || null } : feature,
      ),
    )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="border-b">
          <DialogTitle className="text-base">Edit product/service snapshot</DialogTitle>
          <DialogDescription>
            What the agent has captured about the product/service so far.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Name</Label>
            <Input
              value={draft.offer_name ?? ''}
              onChange={(event) => patch('offer_name', event.target.value || null)}
              placeholder="e.g. Acme"
              className="h-8 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Website</Label>
            <Input
              value={draft.website_url ?? ''}
              onChange={(event) => patch('website_url', event.target.value || null)}
              placeholder="https://"
              className="h-8 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Description</Label>
            <Textarea
              value={draft.offer_description ?? ''}
              onChange={(event) =>
                patch('offer_description', event.target.value || null)
              }
              className="min-h-20 resize-none text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Intent</Label>
            <Input
              value={draft.intent ?? ''}
              onChange={(event) => patch('intent', event.target.value || null)}
              placeholder="What the user is trying to accomplish"
              className="h-8 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Problem solved</Label>
            <Textarea
              value={draft.problem_solved ?? ''}
              onChange={(event) =>
                patch('problem_solved', event.target.value || null)
              }
              className="min-h-20 resize-none text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">How it works</Label>
            <Textarea
              value={draft.how_it_works ?? ''}
              onChange={(event) =>
                patch('how_it_works', event.target.value || null)
              }
              className="min-h-20 resize-none text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Target geography</Label>
            <TagEditor
              value={draft.target_geo}
              onChange={(target_geo) => patch('target_geo', target_geo)}
              placeholder="Add country/region"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-medium">Features</Label>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                className="cursor-pointer text-muted-foreground"
                onClick={() =>
                  patch('features', [
                    ...draft.features,
                    { name: null, description: null, differentiator: null },
                  ])
                }
                aria-label="Add feature"
              >
                <Plus className="size-4" />
              </Button>
            </div>
            {draft.features.length === 0 && (
              <span className="text-xs text-muted-foreground italic">
                No features captured.
              </span>
            )}
            <div className="flex flex-col gap-2">
              {draft.features.map((feature, index) => (
                <div
                  key={index}
                  className="flex flex-col gap-1.5 rounded-lg border border-primary/10 p-2"
                >
                  <div className="flex items-center gap-1.5">
                    <Input
                      value={feature.name ?? ''}
                      onChange={(event) =>
                        patchFeature(index, 'name', event.target.value)
                      }
                      placeholder="Feature name"
                      className="h-8 text-xs"
                    />
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      className="shrink-0 cursor-pointer text-muted-foreground"
                      onClick={() =>
                        patch(
                          'features',
                          draft.features.filter((_, i) => i !== index),
                        )
                      }
                      aria-label="Remove feature"
                    >
                      <X className="size-3.5" />
                    </Button>
                  </div>
                  <Textarea
                    value={feature.description ?? ''}
                    onChange={(event) =>
                      patchFeature(index, 'description', event.target.value)
                    }
                    placeholder="What this feature does"
                    className="min-h-14 resize-none text-xs"
                  />
                  <Input
                    value={feature.differentiator ?? ''}
                    onChange={(event) =>
                      patchFeature(index, 'differentiator', event.target.value)
                    }
                    placeholder="Differentiator"
                    className="h-8 text-xs"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter className="border-t">
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="cursor-pointer"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950"
              onClick={() => {
                onSave(draft)
                onOpenChange(false)
              }}
            >
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface MarketDraft extends MarketExtraction {}

function EditMarketDialog({
  open,
  onOpenChange,
  value,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  value: MarketDraft
  onSave: (value: MarketDraft) => void
}) {
  const [draft, setDraft] = useState<MarketDraft>(() => clone(value))

  useEffect(() => {
    if (open) setDraft(clone(value))
  }, [open, value])

  const patch = <K extends keyof MarketDraft>(
    key: K,
    val: MarketDraft[K],
  ) => setDraft((prev) => ({ ...prev, [key]: val }))

  const patchPricing = <K extends keyof Pricing>(
    index: number,
    key: K,
    val: Pricing[K],
  ) =>
    patch(
      'pricing',
      draft.pricing.map((tier, i) =>
        i === index ? { ...tier, [key]: val } : tier,
      ),
    )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="border-b">
          <DialogTitle className="text-base">Edit market data</DialogTitle>
          <DialogDescription>
            Structured market definition and product-market fit.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Buyer type</Label>
            <ChoiceChips<BuyerType>
              options={BUYER_TYPES}
              value={draft.buyer_type}
              onChange={(buyer_type) => patch('buyer_type', buyer_type)}
              unsetLabel="Unset"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Category</Label>
            <ChoiceChips<ProductCategory>
              options={PRODUCT_CATEGORIES}
              value={draft.category}
              onChange={(category) => patch('category', category)}
              unsetLabel="Unset"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Target audience</Label>
            <Textarea
              value={draft.target_audience ?? ''}
              onChange={(event) =>
                patch('target_audience', event.target.value || null)
              }
              className="min-h-20 resize-none text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Target geography</Label>
            <TagEditor
              value={draft.target_geo}
              onChange={(target_geo) => patch('target_geo', target_geo)}
              placeholder="Add country/region"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-medium">Pricing</Label>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                className="cursor-pointer text-muted-foreground"
                onClick={() =>
                  patch('pricing', [
                    ...draft.pricing,
                    {
                      tier: '',
                      monthly_sub: null,
                      yearly_sub: null,
                      features: [],
                    },
                  ])
                }
                aria-label="Add pricing tier"
              >
                <Plus className="size-4" />
              </Button>
            </div>
            {draft.pricing.length === 0 && (
              <span className="text-xs text-muted-foreground italic">
                No pricing tiers.
              </span>
            )}
            <div className="flex flex-col gap-2">
              {draft.pricing.map((tier, index) => (
                <div
                  key={index}
                  className="flex flex-col gap-1.5 rounded-lg border border-primary/10 p-2"
                >
                  <div className="flex items-center gap-1.5">
                    <Input
                      value={tier.tier}
                      onChange={(event) => patchPricing(index, 'tier', event.target.value)}
                      placeholder="Tier"
                      className="h-8 text-xs"
                    />
                    <Input
                      value={tier.monthly_sub ?? ''}
                      onChange={(event) =>
                        patchPricing(
                          index,
                          'monthly_sub',
                          event.target.value.trim() === '' ? null : event.target.value,
                        )
                      }
                      placeholder="Monthly"
                      className="h-8 text-xs"
                    />
                    <Input
                      value={tier.yearly_sub ?? ''}
                      onChange={(event) =>
                        patchPricing(
                          index,
                          'yearly_sub',
                          event.target.value.trim() === '' ? null : event.target.value,
                        )
                      }
                      placeholder="Yearly"
                      className="h-8 text-xs"
                    />
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      className="shrink-0 cursor-pointer text-muted-foreground"
                      onClick={() =>
                        patch(
                          'pricing',
                          draft.pricing.filter((_, i) => i !== index),
                        )
                      }
                      aria-label="Remove tier"
                    >
                      <X className="size-3.5" />
                    </Button>
                  </div>
                  <TagEditor
                    value={tier.features}
                    onChange={(features) => patchPricing(index, 'features', features)}
                    placeholder="Add included feature"
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Pricing source</Label>
            <ChoiceChips<PricingSource>
              options={['site', 'market_suggestion']}
              value={draft.pricing_source}
              onChange={(pricing_source) => patch('pricing_source', pricing_source)}
              unsetLabel="Unset"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Market fit</Label>
            <ChoiceChips<MarketFitVerdict>
              options={FIT_VERDICTS}
              value={draft.market_fit}
              onChange={(market_fit) => patch('market_fit', market_fit)}
              unsetLabel="Unset"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Fit reasoning</Label>
            <Textarea
              value={draft.market_fit_reasoning ?? ''}
              onChange={(event) =>
                patch('market_fit_reasoning', event.target.value || null)
              }
              className="min-h-20 resize-none text-sm"
            />
          </div>
        </div>
        <DialogFooter className="border-t">
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="cursor-pointer"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950"
              onClick={() => {
                onSave(draft)
                onOpenChange(false)
              }}
            >
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface IcpDraft extends ICP {}

function EditIcpDialog({
  open,
  onOpenChange,
  value,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  value: IcpDraft
  onSave: (value: IcpDraft) => void
}) {
  const [draft, setDraft] = useState<IcpDraft>(() => clone(value))

  useEffect(() => {
    if (open) setDraft(clone(value))
  }, [open, value])

  const patch = <K extends keyof IcpDraft>(key: K, val: IcpDraft[K]) =>
    setDraft((prev) => ({ ...prev, [key]: val }))

  const patchLead = (index: number, key: keyof CompetitorLead, val: string | string[]) =>
    patch(
      'competitor_leads',
      draft.competitor_leads.map((lead, i) =>
        i === index ? { ...lead, [key]: val } : lead,
      ),
    )

  const tagSection = (
    label: string,
    key: keyof Pick<
      IcpDraft,
      | 'industries'
      | 'company_sizes'
      | 'geo'
      | 'buyer_titles'
      | 'exclusions'
      | 'pain_signals'
      | 'intent_keywords'
    >,
    placeholder: string,
  ) => (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs font-medium">{label}</Label>
      <TagEditor
        value={draft[key]}
        onChange={(val) => patch(key, val)}
        placeholder={placeholder}
      />
    </div>
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="border-b">
          <DialogTitle className="text-base">Edit ICP</DialogTitle>
          <DialogDescription>
            Ideal customer profile synthesised by the GTM specialist.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Product/service name</Label>
            <Input
              value={draft.product_name ?? ''}
              onChange={(event) => patch('product_name', event.target.value || null)}
              placeholder="e.g. Acme"
              className="h-8 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium">Buyer type</Label>
            <Input
              value={draft.buyer_type ?? ''}
              onChange={(event) => patch('buyer_type', event.target.value || null)}
              placeholder="B2B, B2C, or both"
              className="h-8 text-sm"
            />
          </div>
          {tagSection('Industries', 'industries', 'Add industry')}
          {tagSection('Company sizes', 'company_sizes', 'Add size band')}
          {tagSection('Geography', 'geo', 'Add geography')}
          {tagSection('Buyer titles', 'buyer_titles', 'Add title')}
          {tagSection('Exclusions', 'exclusions', 'Add exclusion')}
          {tagSection('Pain signals', 'pain_signals', 'Add pain signal')}
          {tagSection('Intent keywords', 'intent_keywords', 'Add keyword')}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-medium">Competitor leads</Label>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                className="cursor-pointer text-muted-foreground"
                onClick={() =>
                  patch('competitor_leads', [
                    ...draft.competitor_leads,
                    { competitor_name: '', search_queries: [], pain_angles: [] },
                  ])
                }
                aria-label="Add competitor lead"
              >
                <Plus className="size-4" />
              </Button>
            </div>
            {draft.competitor_leads.length === 0 && (
              <span className="text-xs text-muted-foreground italic">
                No competitor leads.
              </span>
            )}
            <div className="flex flex-col gap-2">
              {draft.competitor_leads.map((lead, index) => (
                <div
                  key={index}
                  className="flex flex-col gap-2 rounded-lg border border-primary/10 p-2"
                >
                  <div className="flex items-center gap-1.5">
                    <Input
                      value={lead.competitor_name}
                      onChange={(event) =>
                        patchLead(index, 'competitor_name', event.target.value)
                      }
                      placeholder="Competitor name"
                      className="h-8 text-xs"
                    />
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      className="shrink-0 cursor-pointer text-muted-foreground"
                      onClick={() =>
                        patch(
                          'competitor_leads',
                          draft.competitor_leads.filter((_, i) => i !== index),
                        )
                      }
                      aria-label="Remove lead"
                    >
                      <X className="size-3.5" />
                    </Button>
                  </div>
                  <TagEditor
                    value={lead.search_queries}
                    onChange={(search_queries) =>
                      patchLead(index, 'search_queries', search_queries)
                    }
                    placeholder="Add search query"
                  />
                  <TagEditor
                    value={lead.pain_angles}
                    onChange={(pain_angles) =>
                      patchLead(index, 'pain_angles', pain_angles)
                    }
                    placeholder="Add pain angle"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter className="border-t">
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="cursor-pointer"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950"
              onClick={() => {
                onSave(draft)
                onOpenChange(false)
              }}
            >
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const EMPTY_PRODUCT_STATE: ProductState = {
  product_snapshot: null,
  product_domain_understanding: null,
  product_market_fit_understanding: null,
  market_data: null,
  icp: null,
}

function normalizeMarket(market: MarketDataDto | null): MarketExtraction | null {
  if (!market) return null
  return {
    buyer_type: (market.buyer_type ?? null) as BuyerType | null,
    category: (market.category ?? null) as ProductCategory | null,
    target_audience: market.target_audience ?? null,
    // The agent's market extraction does not carry pricing tables; the tab
    // shows an empty pricing section until one is edited in.
    pricing: [],
    pricing_source: null,
    target_geo: market.target_geo ?? [],
    market_fit: (market.market_fit ?? null) as MarketFitVerdict | null,
    market_fit_reasoning: market.market_fit_reasoning ?? null,
  }
}

function buildProductState(args: {
  sessionSnapshot: OfferSnapshot | null
  insights: WorkspaceInsights | null
  phaseResults: PhaseResults | undefined
}): ProductState {
  const { sessionSnapshot, insights, phaseResults } = args
  const marketRun = phaseResults?.understand_market
  const icpRun = phaseResults?.determine_icp as IcpDto | null | undefined
  return {
    product_snapshot: sessionSnapshot ?? insights?.offer_snapshot ?? null,
    product_domain_understanding:
      phaseResults?.understand_offer ??
      insights?.domain_understanding ??
      null,
    product_market_fit_understanding:
      marketRun?.product_market_fit_understanding ??
      insights?.market_fit_understanding ??
      null,
    market_data: normalizeMarket(
      marketRun?.market_data ?? insights?.market_data ?? null,
    ),
    icp: icpRun ?? insights?.icp ?? null,
  }
}

export function ProductComponent({ workspaceId }: { workspaceId?: string }) {
  const { product: sessionProduct, workspaceId: sessionWorkspaceId } = useSession()
  const { insights } = useInsights(workspaceId)
  const run = useAgentRun()

  const [state, setState] = useState<ProductState>(EMPTY_PRODUCT_STATE)
  // Once the user edits a field locally, fetched data no longer overwrites it.
  const editedRef = useRef(false)

  const runBelongsToWorkspace =
    workspaceId !== undefined && run.workspaceId === workspaceId
  const phaseResults = runBelongsToWorkspace ? run.phaseResults : undefined
  const sessionSnapshot =
    sessionWorkspaceId !== null && sessionWorkspaceId === workspaceId
      ? sessionProduct
      : null

  useEffect(() => {
    ensureInsightsLoaded(workspaceId)
  }, [workspaceId])

  useEffect(() => {
    if (editedRef.current) return
    setState(
      buildProductState({ sessionSnapshot, insights, phaseResults }),
    )
  }, [insights, sessionSnapshot, phaseResults])

  const applyEdit = (updater: (prev: ProductState) => ProductState) => {
    editedRef.current = true
    setState(updater)
  }

  const [editInsight, setEditInsight] = useState<
    'domain' | 'market' | null
  >(null)
  const [snapshotEditOpen, setSnapshotEditOpen] = useState(false)
  const [marketEditOpen, setMarketEditOpen] = useState(false)
  const [icpEditOpen, setIcpEditOpen] = useState(false)

  const productName = state.product_snapshot?.offer_name ?? 'your product/service'

  const hasProductContent = Boolean(
    state.product_snapshot ||
      state.product_domain_understanding ||
      state.product_market_fit_understanding ||
      state.market_data ||
      state.icp,
  )

  const snapshot = state.product_snapshot
  const market = state.market_data
  const icp = state.icp

  // The competition stage's two outputs, read live off the run when it is
  // streaming and off the persisted insights otherwise. `swod` is the
  // offer-vs-standard judgment; `profile` is the archetype construct and is the
  // stage's primary output. They are siblings on the same frame, so they are
  // read together rather than one being allowed to appear without the other.
  const competitionRun = phaseResults?.understand_competition
  const liveSwod = competitionRun?.swod ?? insights?.competition_data ?? null
  const liveProfile =
    competitionRun?.profile ?? insights?.ideal_competitor_profile ?? null

  const [tab, setTab] = useState<OfferTab>('product')

  // Whether the agent is still producing output for this workspace right now.
  // Distinguishing "has not got to this stage yet" from "got there and found
  // nothing" needs this, because in both cases the tab is empty and only one of
  // them means the user should wait.
  const runInFlight =
    runBelongsToWorkspace &&
    (run.stage === 'running' || run.stage === 'connecting')

  /** A sub-tab's state: filled, decided-and-empty, or not reached yet. */
  const readiness = (
    hasContent: boolean,
    reached: boolean,
  ): boolean | null => {
    if (hasContent) return true
    return runInFlight && !reached ? null : false
  }

  const offerTabReadiness: Record<OfferTab, boolean | null> = {
    product: readiness(
      Boolean(state.product_snapshot ?? state.product_domain_understanding),
      phaseResults?.understand_offer !== undefined,
    ),
    market: readiness(
      Boolean(state.market_data ?? state.product_market_fit_understanding),
      phaseResults?.understand_market !== undefined,
    ),
    competition: readiness(
      liveProfile !== null || liveSwod !== null,
      competitionRun !== undefined,
    ),
    icp: readiness(icp !== null, phaseResults?.determine_icp !== undefined),
  }

  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 mb-5">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-medium text-foreground">Offer</h2>
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[12px] font-medium text-amber-500">
            <Bot className="size-4.5" />
            agent capture
          </span>
        </div>
        <span className="truncate text-[12px] text-muted-foreground">{productName}</span>
      </div>

      <hr className="mb-3"/>

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as OfferTab)}
        className="mt-3 flex min-h-0 flex-1 flex-col gap-3"
      >
        <OfferTabNav readiness={offerTabReadiness} />

        <TabsContent value="product" className="min-h-0 flex-1 overflow-y-auto pb-2">
          {!hasProductContent ? (
            <EmptyProduct productName={productName} />
          ) : (
            <div className="flex flex-col gap-3">
          <SectionCard
            icon={<Bot className="size-4.5" />}
            title="Agent understanding"
            description="How the agent summarises the product/service
          "
          >
            <AgentInsight
              label="Domain understanding"
              value={state.product_domain_understanding}
              onEdit={() => setEditInsight('domain')}
            />
            <AgentInsight
              label="Market-fit understanding"
              value={state.product_market_fit_understanding}
              onEdit={() => setEditInsight('market')}
            />
          </SectionCard>
            </div>
          )}
        </TabsContent>

        <TabsContent value="market" className="min-h-0 flex-1 overflow-y-auto pb-2">
          <div className="flex flex-col gap-3">
          {snapshot && (
            <SectionCard
              icon={<Package className="size-4" />}
              title="Product/Service snapshot"
              description="Captured profile of the product/service"
              onEdit={() => setSnapshotEditOpen(true)}
            >
              <Row label="Name" value={snapshot.offer_name ?? '—'} />
              <Row
                label="Website"
                value={
                  snapshot.website_url ? (
                    <a
                      href={snapshot.website_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-amber-500 hover:text-amber-400 hover:underline"
                    >
                      {snapshot.website_url}
                      <ExternalLink className="size-3" />
                    </a>
                  ) : (
                    '—'
                  )
                }
              />
              <Row
                label="Description"
                value={snapshot.offer_description ?? '—'}
              />
              <Row label="Intent" value={snapshot.intent ?? '—'} />
              <Row
                label="Problem solved"
                value={snapshot.problem_solved ?? '—'}
              />
              <Row
                label="How it works"
                value={snapshot.how_it_works ?? '—'}
              />
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-medium inline-flex tracking-wide text-foreground uppercase">
                  <CornerRightDown className="h-3.5 w-3.5"/>
                  Features
                </span>
                {snapshot.features.length === 0 ? (
                  <span className="text-sm text-muted-foreground italic">—</span>
                ) : (
                  <div className="flex flex-col gap-2">
                    {snapshot.features.map((feature, index) => (
                      <div
                        key={index}
                        className="rounded-lg border border-primary/10 p-2"
                      >
                        <p className="text-sm font-medium text-foreground">
                          {feature.name ?? 'Untitled feature'}
                        </p>
                        {feature.description && (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {feature.description}
                          </p>
                        )}
                        {feature.differentiator && (
                          <p className="mt-0.5 text-xs text-amber-500/90">
                            {feature.differentiator}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <Row label="Target geography" value={<TagPills items={snapshot.target_geo} />} />
            </SectionCard>
          )}
          {market && (
            <SectionCard
              icon={<Globe className="size-4" />}
              title="Market & fit"
              description="Market definition and product-market fit"
              onEdit={() => setMarketEditOpen(true)}
            >
              <Row label="Buyer type" value={market.buyer_type ?? '—'} />
              <Row label="Category" value={market.category ?? '—'} />
              <Row
                label="Target audience"
                value={market.target_audience ?? '—'}
              />
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-medium inline-flex tracking-wide text-foreground uppercase">
                  <CornerRightDown className="h-3.5 w-3.5"/>
                  Pricing
                </span>
                {market.pricing.length === 0 ? (
                  <span className="text-sm text-muted-foreground italic">—</span>
                ) : (
                  <div className="divide-y divide-border rounded-lg border border-primary/10">
                    {market.pricing.map((tier) => (
                      <div
                        key={tier.tier}
                        className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-0.5 px-3 py-2"
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-foreground">
                            {tier.tier}
                          </p>
                          {tier.features.length > 0 && (
                            <p className="truncate text-xs text-muted-foreground">
                              {tier.features.join(' · ')}
                            </p>
                          )}
                        </div>
                        <div className="text-right text-xs text-muted-foreground">
                          <p>{tier.monthly_sub ?? '—'} /mo</p>
                          <p>{tier.yearly_sub ?? '—'} /yr</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <Row
                label="Pricing source"
                value={
                  market.pricing_source === 'site'
                    ? 'From product site'
                    : market.pricing_source === 'market_suggestion'
                      ? 'Market suggestion'
                      : '—'
                }
              />
              <Row
                label="Target geography"
                value={<TagPills items={market.target_geo} />}
              />
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-medium inline-flex tracking-wide text-foreground uppercase">
                  <CornerRightDown className="h-3.5 w-3.5"/>
                  Market fit
                </span>
                <div className="flex items-center gap-2">
                  {market.market_fit ? (
                    <VerdictBadge verdict={market.market_fit} />
                  ) : (
                    <span className="text-sm text-muted-foreground italic">—</span>
                  )}
                </div>
                {market.market_fit_reasoning && (
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {market.market_fit_reasoning}
                  </p>
                )}
              </div>
            </SectionCard>
          )}
          </div>
        </TabsContent>

        <TabsContent value="competition" className="min-h-0 flex-1 overflow-y-auto pb-2">
          <CompetitionPanel profile={liveProfile} swod={liveSwod} />
        </TabsContent>

        <TabsContent value="icp" className="min-h-0 flex-1 overflow-y-auto pb-2">
          <div className="flex flex-col gap-3">
          {icp && (
            <SectionCard
              icon={<UserRoundCheck className="size-4" />}
              title="Ideal customer profile"
              description="Who to target and how to reach them"
              onEdit={() => setIcpEditOpen(true)}
            >
              <Row label="Product" value={icp.product_name ?? '—'} />
              <Row label="Buyer type" value={icp.buyer_type ?? '—'} />
              <Row label="Industries" value={<TagPills items={icp.industries} />} />
              <Row
                label="Company sizes"
                value={<TagPills items={icp.company_sizes} />}
              />
              <Row label="Geography" value={<TagPills items={icp.geo} />} />
              <Row
                label="Buyer titles"
                value={<TagPills items={icp.buyer_titles} />}
              />
              <Row
                label="Exclusions"
                value={<TagPills items={icp.exclusions} />}
              />
              <Row
                label="Pain signals"
                value={<TagPills items={icp.pain_signals} />}
              />
              <Row
                label="Intent keywords"
                value={<TagPills items={icp.intent_keywords} />}
              />
              <div className="flex flex-col gap-1">
                <span className="text-[11px] font-medium inline-flex tracking-wide text-foreground uppercase">
                  <CornerRightDown className="h-3.5 w-3.5"/>
                  Competitor leads
                </span>
                {icp.competitor_leads.length === 0 ? (
                  <span className="text-sm text-muted-foreground italic">—</span>
                ) : (
                  <div className="flex flex-col gap-2">
                    {icp.competitor_leads.map((lead) => (
                      <div
                        key={lead.competitor_name}
                        className="rounded-lg border border-primary/10 p-2"
                      >
                        <p className="text-sm font-semibold text-foreground">
                          {lead.competitor_name}
                        </p>
                        {lead.search_queries.length > 0 && (
                          <div className="mt-1.5 flex flex-col gap-0.5">
                            <span className="text-[10px] tracking-wide text-muted-foreground uppercase">
                              Search queries
                            </span>
                            <TagPills items={lead.search_queries} />
                          </div>
                        )}
                        {lead.pain_angles.length > 0 && (
                          <div className="mt-1.5 flex flex-col gap-0.5">
                            <span className="text-[10px] tracking-wide text-muted-foreground uppercase">
                              Pain angles
                            </span>
                            <ul className="flex list-disc flex-col gap-0.5 pl-4 text-xs text-muted-foreground">
                              {lead.pain_angles.map((angle) => (
                                <li key={angle}>{angle}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </SectionCard>
          )}
          </div>
        </TabsContent>
      </Tabs>

      <EditTextDialog
        open={editInsight === 'domain'}
        onOpenChange={(open) => !open && setEditInsight(null)}
        title="Edit domain understanding"
        description="How the product/service fits into its domain/category (target ~40 words)."
        value={state.product_domain_understanding ?? ''}
        onSave={(value) =>
          applyEdit((prev) => ({
            ...prev,
            product_domain_understanding: value,
          }))
        }
      />
      <EditTextDialog
        open={editInsight === 'market'}
        onOpenChange={(open) => !open && setEditInsight(null)}
        title="Edit market-fit understanding"
        description="How well the product/service fits its market (target ~40 words)."
        value={state.product_market_fit_understanding ?? ''}
        onSave={(value) =>
          applyEdit((prev) => ({
            ...prev,
            product_market_fit_understanding: value,
          }))
        }
      />
      {snapshot && (
        <EditSnapshotDialog
          open={snapshotEditOpen}
          onOpenChange={setSnapshotEditOpen}
          value={snapshot}
          onSave={(value) =>
            applyEdit((prev) => ({ ...prev, product_snapshot: value }))
          }
        />
      )}
      {market && (
        <EditMarketDialog
          open={marketEditOpen}
          onOpenChange={setMarketEditOpen}
          value={market}
          onSave={(value) =>
            applyEdit((prev) => ({ ...prev, market_data: value }))
          }
        />
      )}
      {icp && (
        <EditIcpDialog
          open={icpEditOpen}
          onOpenChange={setIcpEditOpen}
          value={icp}
          onSave={(value) => applyEdit((prev) => ({ ...prev, icp: value }))}
        />
      )}
    </div>
  )
}

export default ProductComponent