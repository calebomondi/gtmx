import { useState } from 'react'
import {
  AlertTriangle,
  ArrowUpRight,
  ChevronRight,
  Code2,
  ExternalLink,
  BadgeCheck,
  Hash,
  Pencil,
  Quote,
  Trash2,
  Globe,
  Sparkles,
  Target,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { formatRelativeTime } from '@/lib/format'
import { cn } from 'cn'

import {
  TRACKING_KIND_LABELS,
  unsourcedFieldLabel,
  type Competitor,
  type Confidence,
  type SocialProfile,
  type SourcedClaim,
  type TrackingSource,
  type TrackingSourceKind,
} from './competition-types'

/**
 * ONE COMPETITOR, AND WHY IT IS BUILT THE WAY IT IS
 * ------------------------------------------------
 * The design problem on this tab is not layout. It is that a researched claim
 * and a hallucinated one are visually identical: both arrive as a confident
 * sentence about a real company, and nothing on screen distinguishes them. The
 * backend refuses to store a sourced claim without its quote, so the quote is
 * always in hand — and it is rendered *inline and always visible*, in a left-
 * bordered citation style, rather than behind a hover or a disclosure.
 *
 * Collapsing happens at the level of SECTIONS, never at the level of evidence.
 * A section the user opened shows its quotes.
 *
 * The second rule is that "we looked and found nothing" must never look like
 * "there was nothing to find". An absent field renders as an explicit
 * "not found", and the card says how much of the profile came back empty. A
 * card that is quietly full of dashes reads as researched and came up short,
 * which is the opposite of the truth.
 */

// ---------------------------------------------------------------------------
// Small primitives
// ---------------------------------------------------------------------------

/** A fact research could not establish.
 *
 * Says "not found" rather than an em dash, and carries the field's name, so
 * "not found" reads as a search that came up short rather than a field that
 * does not exist. */
function NotFound({ field }: { field: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-[12px] text-muted-foreground/80">
      <AlertTriangle className="size-3 shrink-0" />
      <span className="italic">
        not found &mdash; research could not establish the {unsourcedFieldLabel(field)}
      </span>
    </span>
  )
}

function Fact({
  label,
  field,
  value,
}: {
  label: string
  field: string
  value: string | null | undefined
}) {
  const text = value?.trim()
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {text ? (
        <span className="text-[13px] leading-relaxed text-foreground">
          {text}
        </span>
      ) : (
        <NotFound field={field} />
      )}
    </div>
  )
}

/** A claim, with the quote that backs it, always visible.
 *
 * The claim is the assertion; the quote is why we are willing to make it. The
 * left border is the app's amber accent, which ties the citation to the amber
 * "agent" identity used elsewhere on this tab — this is a line the agent read
 * off a page, not a line it composed. */
function ClaimItem({
  claim,
  tone = 'neutral',
}: {
  claim: SourcedClaim
  tone?: 'neutral' | 'negative'
}) {
  return (
    <li className="flex flex-col gap-1">
      <span className="text-[13px] leading-relaxed text-foreground">
        {claim.text}
      </span>
      <div
        className={cn(
          'flex items-start gap-1.5 border-l-2 py-0.5 pl-2.5',
          tone === 'negative' ? 'border-rose-500/40' : 'border-amber-500/40',
        )}
      >
        <Quote className="mt-0.5 size-3 shrink-0 text-muted-foreground/60" />
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-[12px] leading-relaxed text-muted-foreground italic">
            {claim.evidence}
          </span>
          {claim.source_url && (
            <a
              href={claim.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-fit items-center gap-0.5 text-[11px] text-blue-500 hover:text-blue-400 hover:underline"
            >
              source
              <ArrowUpRight className="size-2.5" />
            </a>
          )}
        </span>
      </div>
    </li>
  )
}

function ClaimList({
  claims,
  tone,
  emptyNote,
}: {
  claims: SourcedClaim[]
  tone?: 'neutral' | 'negative'
  /** Shown when the list is empty.
   *
   * Required, because an empty pain-signal list and an empty strengths list
   * mean opposite things and must not render the same way. */
  emptyNote: string
}) {
  if (claims.length === 0) {
    return <p className="text-[12px] text-muted-foreground italic">{emptyNote}</p>
  }
  return (
    <ul className="flex flex-col gap-2.5">
      {claims.map((claim, i) => (
        <ClaimItem key={`${claim.text}-${i}`} claim={claim} tone={tone} />
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Socials
// ---------------------------------------------------------------------------

/** Brand marks come from the repo's own `/public` set, the same files
 * `social-connect.tsx` uses, rather than from an icon library. lucide dropped
 * its brand glyphs in v1, and reaching for a generic `AtSign` would make
 * Instagram and X indistinguishable in a row whose entire job is telling you
 * which network to watch. X and GitHub have no mark in the set, so they get
 * the closest neutral glyph available. */
const SOCIAL_MARKS: Record<
  string,
  | { kind: 'image'; src: string; size: string; chip?: string }
  | { kind: 'icon'; icon: LucideIcon }
> = {
  instagram: { kind: 'image', src: '/instagram.svg', size: 'size-3.5' },
  tiktok: {
    kind: 'image',
    src: '/tiktok-mark.svg',
    size: 'size-3',
    // The TikTok mark's note is white, so it needs the dark chip the other
    // brands carry as part of their own shape. Without it the cyan/magenta
    // offsets are all you see.
    chip: 'bg-neutral-900 dark:bg-black',
  },
  linkedin: { kind: 'image', src: '/linkedin-mark.svg', size: 'size-3.5' },
  // No X or GitHub mark in public/ — these two are the compromise.
  x: { kind: 'icon', icon: Hash },
  github: { kind: 'icon', icon: Code2 },
}

function SocialGlyph({ kind }: { kind: TrackingSourceKind }) {
  const mark = SOCIAL_MARKS[kind] ?? { kind: 'icon' as const, icon: Globe }
  if (mark.kind === 'image') {
    return (
      <span
        className={cn(
          'inline-flex shrink-0 items-center justify-center rounded-[3px]',
          mark.size,
          mark.chip,
        )}
      >
        <img src={mark.src} alt="" className="size-full" aria-hidden />
      </span>
    )
  }
  const Icon = mark.icon
  return <Icon className="size-3 shrink-0 text-muted-foreground" />
}

/** A real type guard rather than a cast, so an unrecognised network keeps
 * flowing through as 'other' without loosening the label record's key type. */
function isKnownKind(kind: string): kind is TrackingSourceKind {
  return Object.prototype.hasOwnProperty.call(TRACKING_KIND_LABELS, kind)
}

function kindOf(source: TrackingSource): TrackingSourceKind {
  const kind = source.kind.toLowerCase()
  return isKnownKind(kind) ? kind : 'other'
}

const CONFIDENCE_TONE: Record<Confidence, string> = {
  // Only a high-confidence handle is presented as a solid link. A handle that
  // sat next to a company name in a directory is shown as tentative, because
  // following it can land the user on a different business with a similar name.
  high: 'border-foreground/15 bg-background hover:border-foreground/30',
  medium: 'border-dashed border-foreground/20 bg-background/50',
  low: 'border-dashed border-foreground/15 bg-background/30',
}

function SocialChip({ source }: { source: TrackingSource }) {
  const kind = kindOf(source)
  const confidence = source.confidence ?? null
  const isUrl = /^https?:\/\//i.test(source.value)
  const tone = confidence ? CONFIDENCE_TONE[confidence] : CONFIDENCE_TONE.medium

  const body = (
    <>
      <SocialGlyph kind={kind} />
      <span className="truncate">{TRACKING_KIND_LABELS[kind]}</span>
      {isUrl && <ArrowUpRight className="size-2.5 shrink-0 text-muted-foreground/60" />}
    </>
  )

  const classes = cn(
    'inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-[12px]',
    'text-foreground/90 transition-colors',
    tone,
    isUrl && 'cursor-pointer',
  )

  if (!isUrl) {
    return (
      <span className={classes} title={source.value}>
        {body}
      </span>
    )
  }

  return (
    <a
      href={source.value}
      target="_blank"
      rel="noreferrer"
      className={classes}
      title={
        confidence && confidence !== 'high'
          ? `${source.value} — ${confidence} confidence this account belongs to this company`
          : source.value
      }
    >
      {body}
    </a>
  )
}

function Socials({ sources }: { sources: TrackingSource[] }) {
  if (sources.length === 0) {
    return (
      <p className="text-[12px] text-muted-foreground italic">
        not found &mdash; no social profiles could be tied to this company
      </p>
    )
  }
  const graded = sources.filter((s) => s.confidence && s.confidence !== 'high')
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source, i) => (
          <SocialChip key={`${source.kind}-${source.value}-${i}`} source={source} />
        ))}
      </div>
      {graded.length > 0 && (
        <p className="text-[11px] leading-relaxed text-muted-foreground/80">
          Dashed links are lower confidence &mdash; found next to the company
          name rather than read off its own site. Worth checking before you
          follow one.
        </p>
      )}
    </div>
  )
}

const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })
const SOCIAL_ORDER = ['linkedin', 'x', 'instagram', 'tiktok']

function Stat({ value, label }: { value: number | string | null; label: string }) {
  if (value === null || value === '') return null
  return (
    <span>
      <span className="font-medium text-foreground tabular-nums">
        {typeof value === 'number' ? compact.format(value) : value}
      </span>{' '}
      {label}
    </span>
  )
}

function SocialProfileRow({ profile }: { profile: SocialProfile }) {
  const kind = isKnownKind(profile.platform) ? profile.platform : 'other'
  const latest = profile.recent_posts[0]
  return (
    <li className="flex flex-col gap-1.5">
      <a
        href={profile.url}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-1.5 text-[13px] font-medium hover:underline"
      >
        <SocialGlyph kind={kind} />
        {TRACKING_KIND_LABELS[kind]}
        {profile.verified && <BadgeCheck className="size-3.5 text-sky-500" aria-label="verified" />}
        <ArrowUpRight className="size-2.5 text-muted-foreground/60" />
      </a>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[12px] text-muted-foreground">
        <Stat value={profile.followers} label="followers" />
        <Stat value={profile.posts_count} label={profile.platform === 'tiktok' ? 'videos' : 'posts'} />
        <Stat value={profile.likes} label="likes" />
        <Stat value={profile.employees} label="" />
        {profile.followers === null && profile.posts_count === null && <span>counts hidden by the network</span>}
      </div>
      {latest && (
        <a
          href={latest.url ?? profile.url}
          target="_blank"
          rel="noreferrer"
          className="rounded-md bg-muted/50 px-2.5 py-1.5 text-[12px] leading-relaxed text-foreground/85 hover:bg-muted"
        >
          <span className="line-clamp-2">{latest.text || 'Latest post'}</span>
          <span className="mt-0.5 block text-[11px] text-muted-foreground">
            {latest.date ? formatRelativeTime(Date.parse(latest.date)) : 'latest'}
            {latest.likes !== null && ` · ${compact.format(latest.likes)} likes`}
          </span>
        </a>
      )}
    </li>
  )
}

/** What a rival is doing on social, refreshed weekly by monitoring. */
function SocialActivity({ competitor }: { competitor: Competitor }) {
  const profiles = Object.values(competitor.social_profiles ?? {}).sort(
    (a, b) => SOCIAL_ORDER.indexOf(a.platform) - SOCIAL_ORDER.indexOf(b.platform),
  )
  if (profiles.length === 0) {
    return (
      <p className="text-[12px] text-muted-foreground italic">
        {competitor.socials_checked_at
          ? 'no social profiles are linked from their site'
          : 'stats appear after the next check — usually within a few minutes'}
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-3">
        {profiles.map((profile) => (
          <SocialProfileRow key={profile.platform} profile={profile} />
        ))}
      </ul>
      {competitor.socials_checked_at && (
        <p className="text-[11px] text-muted-foreground/80">
          Updated {formatRelativeTime(Date.parse(competitor.socials_checked_at))}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// A collapsible block inside the card
// ---------------------------------------------------------------------------

function Detail({
  title,
  badge,
  defaultOpen,
  children,
}: {
  title: string
  badge?: React.ReactNode
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen ?? false)
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border-t border-border/60">
      <CollapsibleTrigger className="group flex w-full cursor-pointer items-center gap-2 py-2.5 text-left">
        <ChevronRight
          className={cn(
            'size-3.5 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-90',
          )}
        />
        <span className="text-[12px] font-medium uppercase tracking-wide text-foreground/80">
          {title}
        </span>
        {badge}
      </CollapsibleTrigger>
      <CollapsibleContent className="pb-3">{children}</CollapsibleContent>
    </Collapsible>
  )
}

function CountBadge({ n, tone = 'neutral' }: { n: number; tone?: 'neutral' | 'amber' }) {
  return (
    <span
      className={cn(
        'rounded-full px-1.5 py-0.5 text-[11px] font-medium tabular-nums',
        tone === 'amber'
          ? 'bg-amber-500/15 text-amber-500'
          : 'bg-muted px-1.5 text-muted-foreground',
      )}
    >
      {n}
    </span>
  )
}

// ---------------------------------------------------------------------------
// The card
// ---------------------------------------------------------------------------

const SCOPE_LABELS: Record<string, string> = {
  local: 'Local',
  regional: 'Regional',
  global: 'Global',
  any: 'Any',
}

function formatDate(iso: string | null | undefined): string | null {
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

export function CompetitorCard({
  competitor,
  busy,
  onEdit,
  onRemove,
}: {
  competitor: Competitor
  busy?: boolean
  onEdit: (competitor: Competitor) => void
  onRemove: (competitor: Competitor) => void
}) {
  const unsourced = competitor.unsourced_fields ?? []
  const gapCount = unsourced.length

  const scope = competitor.geography_scope?.toLowerCase() ?? null

  return (
    <Card className="border-primary/15">
      <CardHeader className="flex flex-row items-start justify-between gap-2 border-b p-4 pb-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-sm font-semibold text-amber-500">
            {initialOf(competitor.name)}
          </div>
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <CardTitle className="truncate text-sm font-semibold">
                {competitor.name || competitor.domain_key}
              </CardTitle>
              {scope && scope !== 'any' && (
                <span className="rounded-full bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                  {SCOPE_LABELS[scope] ?? scope}
                </span>
              )}
              {competitor.source === 'manual' && (
                <span className="rounded-full bg-blue-500/15 px-1.5 py-0.5 text-[11px] font-medium text-blue-400">
                  added by you
                </span>
              )}
            </div>
            <a
              href={competitor.website}
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-fit items-center gap-1 text-xs text-blue-500 hover:text-blue-400 hover:underline"
            >
              <span className="truncate">{competitor.website}</span>
              <ExternalLink className="size-3 shrink-0" />
            </a>
            {competitor.matched_archetype && (
              <span className="text-[11px] text-muted-foreground">
                matches the &ldquo;{competitor.matched_archetype}&rdquo; archetype
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="cursor-pointer text-muted-foreground"
            onClick={() => onEdit(competitor)}
            aria-label={`Edit ${competitor.name}`}
          >
            <Pencil className="size-3.5" />
          </Button>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            className="cursor-pointer text-muted-foreground hover:text-rose-500"
            onClick={() => onRemove(competitor)}
            aria-label={`Remove ${competitor.name}`}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-3 p-4 pt-3.5">
        {/* -- the headline: what this company is ---------------------- */}
        <Fact
          label="What they do"
          field="description"
          value={competitor.description}
        />

        {/* -- the one place the agent is allowed to be assertive ------ */}
        {competitor.opportunities.length > 0 && (
          <div className="flex flex-col gap-1.5 rounded-lg border border-amber-500/25 bg-amber-500/5 p-2.5">
            <div className="flex items-center gap-1.5">
              <Target className="size-3.5 text-amber-500" />
              <span className="text-[12px] font-medium uppercase tracking-wide text-amber-500">
                Where you could beat them
              </span>
            </div>
            <ul className="flex flex-col gap-1">
              {competitor.opportunities.map((item, i) => (
                <li
                  key={`${item}-${i}`}
                  className="flex gap-1.5 text-[13px] leading-relaxed text-foreground/90"
                >
                  <ArrowUpRight className="mt-0.5 size-3 shrink-0 text-amber-500/70" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <p className="text-[11px] leading-relaxed text-muted-foreground/80">
              The agent&rsquo;s read, drawn from the cited facts above &mdash;
              not something anyone said. Every other field on this card is
              quoted.
            </p>
          </div>
        )}

        {competitor.comparison && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              How they compare to you
            </span>
            <p className="text-[13px] leading-relaxed text-foreground">
              {competitor.comparison}
            </p>
          </div>
        )}

        {/* -- the core facts, two-up ---------------------------------- */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-2.5">
          <Fact
            label="Who they serve"
            field="target_customers"
            value={competitor.target_customers}
          />
          <Fact
            label="Headquarters"
            field="headquarters"
            value={competitor.headquarters}
          />
          <Fact
            label="Pricing"
            field="pricing"
            value={competitor.pricing}
          />
          <Fact
            label="Business model"
            field="business_model"
            value={competitor.business_model}
          />
          <Fact
            label="Offering"
            field="offering"
            value={competitor.offering}
          />
          <Fact
            label="Positioning"
            field="positioning"
            value={competitor.positioning}
          />
        </div>

        {/* -- the socials, which are how you actually watch a rival ----- */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Where to watch them
          </span>
          <Socials sources={competitor.tracking_sources} />
        </div>

        {/* -- the evidence, in sections -------------------------------- */}
        <div className="-mx-1 flex flex-col">
          <Detail
            title="Social activity"
            badge={<CountBadge n={Object.keys(competitor.social_profiles ?? {}).length} />}
          >
            <SocialActivity competitor={competitor} />
          </Detail>

          <Detail
            title="Strengths"
            defaultOpen
            badge={<CountBadge n={competitor.strengths.length} />}
          >
            <ClaimList
              claims={competitor.strengths}
              emptyNote="not found &mdash; research could not establish any strengths"
            />
          </Detail>

          <Detail
            title="Weaknesses"
            badge={<CountBadge n={competitor.weaknesses.length} />}
          >
            <ClaimList
              claims={competitor.weaknesses}
              tone="negative"
              emptyNote="not found &mdash; research could not establish any weaknesses"
            />
          </Detail>

          <Detail
            title="What customers say"
            badge={
              <CountBadge
                n={competitor.customer_sentiment.length}
                tone={competitor.customer_sentiment.length > 0 ? 'amber' : 'neutral'}
              />
            }
          >
            <ClaimList
              claims={competitor.customer_sentiment}
              emptyNote="not found &mdash; no customer commentary was retrievable"
            />
          </Detail>

          <Detail
            title="Pain signals"
            badge={<CountBadge n={competitor.pain_signals.length} />}
          >
            <div className="flex flex-col gap-2">
              <p className="text-[11px] leading-relaxed text-muted-foreground/80">
                Specific, quoted complaints. An empty list means none were
                found &mdash; it is not evidence that this company has none.
              </p>
              <ClaimList
                claims={competitor.pain_signals}
                tone="negative"
                emptyNote="none found"
              />
            </div>
          </Detail>

          {competitor.notable_customers.length > 0 && (
            <Detail
              title="Notable customers"
              badge={<CountBadge n={competitor.notable_customers.length} />}
            >
              <div className="flex flex-wrap gap-1.5">
                {competitor.notable_customers.map((customer, i) => (
                  <span
                    key={`${customer}-${i}`}
                    className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-[12px] text-foreground/90"
                  >
                    <Users className="size-3 text-muted-foreground" />
                    {customer}
                  </span>
                ))}
              </div>
            </Detail>
          )}
        </div>

        {/* -- the user's own note, never the agent's -------------------- */}
        {competitor.notes && (
          <div className="flex flex-col gap-0.5 rounded-lg bg-muted/40 p-2.5">
            <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Your note
            </span>
            <p className="text-[13px] leading-relaxed text-foreground/90">
              {competitor.notes}
            </p>
          </div>
        )}

        {/* -- how complete this profile actually is -------------------- */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border/60 pt-2.5 text-[11px] text-muted-foreground">
          <span>First seen {formatDate(competitor.first_seen_at) ?? '—'}</span>
          <span aria-hidden>·</span>
          <span>
            Last checked {formatDate(competitor.deep_researched_at ?? competitor.last_seen_at) ?? '—'}
          </span>
          {busy && (
            <>
              <span aria-hidden>·</span>
              <span className="inline-flex items-center gap-1 text-amber-500">
                <Sparkles className="size-3" />
                researching now
              </span>
            </>
          )}
          {!busy && gapCount > 0 && (
            <>
              <span aria-hidden>·</span>
              <span
                className="inline-flex items-center gap-1"
                title={`Could not establish: ${unsourced
                  .map(unsourcedFieldLabel)
                  .join(', ')}`}
              >
                <AlertTriangle className="size-3" />
                {gapCount} field{gapCount === 1 ? '' : 's'} not established
              </span>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default CompetitorCard