import { useMemo } from 'react'
import {
  Bot,
  Building2,
  Globe2,
  MapPinned,
  Package,
  Radar,
  UserRoundCheck,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from 'cn'

import type { IdealCompetitorProfileDto } from '@/lib/api'

import { SectionCard, Row, TagPills } from './product-sections'

/**
 * THE OFFER TAB, SPLIT BY WHAT EACH STAGE ANSWERS
 * ----------------------------------------------
 * Four sub-tabs, one per discovery stage, in the order the agent runs them:
 *
 *   Product       what this thing is, and how the agent reads its domain
 *   Market        what world it sells into, and the extracted market structure
 *   Competition   what a rival looks like here -- the IDEAL COMPETITOR PROFILE
 *   ICP           who to go after, which consumes all three above
 *
 * The split follows the spine rather than the data shape, which is the point: a
 * user asking "is my competition understanding any good?" lands on Competition
 * without having to know which of four stacked cards holds it. Four cards in one
 * scroll had also made the tab read as one undifferentiated wall, with the ICP
 * — the output everything else feeds — buried under the bottom.
 *
 * WHY COMPETITION LIVES HERE AND NOT ON THE COMPETITORS TAB
 * ---------------------------------------------------------
 * The two hold different kinds of knowledge and are kept apart on purpose.
 *
 * This tab's Competition sub-tab holds the archetype profile: a construct. It
 * names no company, and the stage was rebuilt to construct it aggressively,
 * because a shape you are looking for cannot be false.
 *
 * The Competitors tab holds real companies. Every field there is a claim about
 * a named business, so each carries the quote it came from, and a company with
 * no public website is dropped. Aggression there would be fabrication.
 *
 * Rendering an archetype in the real-companies list would be indistinguishable
 * on screen from a fabricated company, which is the exact confusion the split
 * exists to prevent. So the profile is presented here as archetypes -- clearly
 * a shape -- and never as a company.
 */

export type OfferTab = 'product' | 'market' | 'competition' | 'icp'

interface OfferTabDef {
  value: OfferTab
  label: string
  icon: LucideIcon
}

/** Order is the spine's order, and it is also the dependency order: the ICP is
 * built from the other three, so it reads last. */
const OFFER_TABS: OfferTabDef[] = [
  { value: 'product', label: 'Product', icon: Package },
  { value: 'market', label: 'Market', icon: Globe2 },
  { value: 'competition', label: 'Competition', icon: Radar },
  { value: 'icp', label: 'ICP', icon: UserRoundCheck },
]

export function OfferTabNav({
  /** Per-tab readiness, so a sub-tab the agent has not filled yet is visibly
   * empty rather than silently blank. `null` means "not decided" -- the run has
   * not reached it -- which is a different state from "decided, nothing found". */
  readiness,
  value,
  onTabChange,
}: {
  readiness: Record<OfferTab, boolean | null>
  value: OfferTab
  onTabChange: (value: OfferTab) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {OFFER_TABS.map(({ value: tabValue, label, icon: Icon }) => {
        const state = readiness[tabValue]
        const active = value === tabValue
        return (
          <button
            key={tabValue}
            type="button"
            onClick={() => onTabChange(tabValue)}
            className={cn(
              'cursor-pointer rounded-full border px-2.5 py-1.5 text-xs font-medium transition-colors flex items-center gap-1.5',
              active
                ? 'border-amber-500 bg-amber-500 text-amber-950'
                : 'border-border bg-secondary text-secondary-foreground hover:bg-accent hover:text-accent-foreground',
            )}
          >
            <Icon className="size-3.5" />
            {label}
            {state === false && (
              <span
                className="size-1.5 rounded-full bg-current/40"
                aria-label="nothing found here yet"
              />
            )}
            {state === null && (
              <span
                className="size-1.5 animate-pulse rounded-full bg-current/40"
                aria-label="the agent has not reached this stage yet"
              />
            )}
          </button>
        )
      })}
    </div>
  )
}

export { OFFER_TABS }

// ---------------------------------------------------------------------------
// Competition sub-tab
// ---------------------------------------------------------------------------

const CONFIDENCE_TONE: Record<string, string> = {
  high: 'bg-emerald-500/15 text-emerald-500',
  medium: 'bg-amber-500/15 text-amber-500',
  low: 'bg-muted text-muted-foreground',
}

function SignalList({
  title,
  icon,
  items,
  tone = 'neutral',
  hint,
}: {
  title: string
  icon: LucideIcon
  items: string[]
  tone?: 'neutral' | 'amber'
  hint?: string
}) {
  if (items.length === 0) return null
  const Icon = icon
  return (
    <div className="flex flex-col gap-1.5">
      <span
        className={cn(
          'flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide',
          tone === 'amber' ? 'text-amber-500' : 'text-muted-foreground',
        )}
      >
        <Icon className="size-3.5" />
        {title}
      </span>
      <ul className="flex list-disc flex-col gap-0.5 pl-4 text-xs leading-relaxed text-muted-foreground">
        {items.map((item, i) => (
          <li key={`${item}-${i}`}>{item}</li>
        ))}
      </ul>
      {hint && (
        <p className="pl-4 text-[11px] leading-relaxed text-muted-foreground/70">
          {hint}
        </p>
      )}
    </div>
  )
}

function ArchetypeCard({
  archetype,
  index,
}: {
  archetype: IdealCompetitorProfileDto['archetypes'][number]
  index: number
}) {
  return (
    <Card className="border-primary/15">
      <CardContent className="flex flex-col gap-2.5 p-3.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex size-5 shrink-0 items-center justify-center rounded-md bg-amber-500/15 text-[11px] font-semibold tabular-nums text-amber-500">
            {index + 1}
          </span>
          <span className="text-[13px] font-semibold text-foreground">
            {archetype.label}
          </span>
          <Badge
            variant="secondary"
            className={cn(
              'border-0 text-[11px] capitalize',
              archetype.geography_scope === 'local' && 'bg-amber-500/15 text-amber-500',
              archetype.geography_scope === 'global' && 'bg-blue-500/15 text-blue-400',
            )}
          >
            {archetype.geography_scope}
          </Badge>
          <Badge
            variant="secondary"
            className={cn(
              'border-0 text-[11px]',
              CONFIDENCE_TONE[archetype.confidence] ?? CONFIDENCE_TONE.low,
            )}
          >
            {archetype.confidence} confidence
          </Badge>
        </div>

        <p className="text-[13px] leading-relaxed text-foreground/90">
          {archetype.archetype_description}
        </p>

        <div className="grid grid-cols-2 gap-x-4 gap-y-2">
          {archetype.typical_offering && (
            <Row label="Typically offers" value={archetype.typical_offering} />
          )}
          {archetype.business_model && (
            <Row label="Business model" value={archetype.business_model} />
          )}
          {archetype.pricing_model && (
            <Row label="Pricing" value={archetype.pricing_model} />
          )}
          {archetype.customer_profile && (
            <Row label="Customer" value={archetype.customer_profile} />
          )}
        </div>

        <SignalList
          title="Likely advantages"
          icon={Building2}
          items={archetype.likely_advantages}
        />
        <SignalList
          title="Likely weaknesses"
          icon={Radar}
          items={archetype.likely_weaknesses}
          hint="Inferred from the shape above rather than observed — these are where a rival of this kind usually gives ground, not complaints we have read."
        />

        <SignalList
          title="Where to find them"
          icon={MapPinned}
          items={archetype.where_to_find_them}
          tone="amber"
          hint="The searches the competitor agent runs for this archetype. No company has been looked up from these yet."
        />
      </CardContent>
    </Card>
  )
}

/** The archetype profile, presented as archetypes and never as companies. */
export function CompetitionPanel({
  profile,
  swod,
}: {
  profile: IdealCompetitorProfileDto | null
  swod: {
    strengths: string[]
    weaknesses: string[]
    opportunities: string[]
    differentiators: string[]
  } | null
}) {
  const archetypes = useMemo(
    () => (profile?.archetypes ?? []).filter((a) => a.label),
    [profile],
  )

  if (!profile && !swod) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-primary/20 bg-muted/30 px-6 py-12 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/15 text-amber-500">
          <Radar className="size-5" />
        </div>
        <p className="text-sm font-medium text-foreground">
          Competition not mapped yet
        </p>
        <p className="max-w-md text-xs leading-relaxed text-muted-foreground">
          The competition stage builds a profile of what a rival looks like in
          your market &mdash; the archetypes, their pricing anchors, the signals
          that mark a new entrant &mdash; without naming any company.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {profile && (
        <SectionCard
          icon={<Radar className="size-4" />}
          title="Ideal competitor profile"
          description="What a perfect competitor looks like in this market — a shape to search for, not a list of companies"
        >
          <Row label="Category" value={profile.category_definition || '—'} />

          {profile.price_anchor_range && (
            <Row label="Price anchor" value={profile.price_anchor_range} />
          )}

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Confidence
            </span>
            <Badge
              variant="secondary"
              className={cn(
                'border-0 text-[11px]',
                CONFIDENCE_TONE[profile.confidence] ?? CONFIDENCE_TONE.low,
              )}
            >
              {profile.confidence}
            </Badge>
          </div>

          <SignalList
            title="Boundary of the category"
            icon={Globe2}
            items={profile.boundary_of_category}
            hint="What is deliberately excluded — a rival outside these lines is a substitute, not a competitor."
          />
          <SignalList
            title="Channels"
            icon={Globe2}
            items={profile.channels}
          />
          <SignalList
            title="Signals a global player is entering"
            icon={Bot}
            items={profile.global_entry_signals}
          />
          <SignalList
            title="Signals a local player is defending"
            icon={MapPinned}
            items={profile.local_defence_signals}
            tone="amber"
          />
          <SignalList
            title="Substitution risks"
            icon={Globe2}
            items={profile.substitution_risks}
            hint="Where customers stop buying a product like yours at all, rather than buying a different one."
          />
        </SectionCard>
      )}

      {archetypes.length > 0 && (
        <SectionCard
          icon={<Radar className="size-4" />}
          title={`Archetypes (${archetypes.length})`}
          description="Each one becomes a search when you look for competitors"
        >
          <div className="flex flex-col gap-2.5">
            {archetypes.map((archetype, index) => (
              <ArchetypeCard
                key={`${archetype.label}-${index}`}
                archetype={archetype}
                index={index}
              />
            ))}
          </div>
        </SectionCard>
      )}

      {swod && (
        <SectionCard
          icon={<Bot className="size-4" />}
          title="Your position against the standard"
          description="How your offer compares to what the market expects"
        >
          <Row label="Strengths" value={<TagPills items={swod.strengths} />} />
          <Row label="Weaknesses" value={<TagPills items={swod.weaknesses} />} />
          <Row
            label="Opportunities"
            value={<TagPills items={swod.opportunities} />}
          />
          <Row
            label="Differentiators"
            value={<TagPills items={swod.differentiators} />}
          />
        </SectionCard>
      )}
    </div>
  )
}