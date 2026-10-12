import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  BadgeCheck,
  Building2,
  CheckCheck,
  Factory,
  MapPin,
  Megaphone,
  Search,
  SearchCheck,
  SearchX,
  Target,
  UserStar,
} from 'lucide-react'

import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { AvatarImg } from '@/components/specialist-avatargroup'
import type {
  CompetitionDataDto,
  IcpDto,
  IdealCompetitorProfileDto,
  MarketDataDto,
  SpecialistDto,
} from '@/lib/api'

// Each panel shows only what the stage actually returned: a field the agent
// left empty is omitted rather than rendered as a blank row or a dash.

const SPECIALIST_BORDERS = ['border-red-500', 'border-green-500', 'border-blue-500', 'border-amber-500']

type Value = string | null | undefined | string[]

function present(value: Value): boolean {
  return Array.isArray(value) ? value.some((v) => v.trim()) : Boolean(value?.trim())
}

function initialsFor(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('')
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="w-full max-w-md rounded-xl p-4">
      <p className="mb-2 text-start text-base font-medium">{title}</p>
      {children}
    </div>
  )
}

function Prose({ text }: { text: Value }) {
  if (!present(text) || Array.isArray(text)) return null
  return <p className="text-start text-sm leading-relaxed text-muted-foreground">{text}</p>
}

function Chips({ items, icon: Icon }: { items: string[]; icon: LucideIcon }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.filter((item) => item.trim()).map((item) => (
        <span key={item} className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground">
          <Icon className="size-3 shrink-0 text-blue-500" />
          {item}
        </span>
      ))}
    </div>
  )
}

/** A label/value table that drops empty rows, and itself when all are empty. */
function Fields({ rows }: { rows: [label: string, value: Value, icon?: LucideIcon][] }) {
  const shown = rows.filter(([, value]) => present(value))
  if (shown.length === 0) return null
  return (
    <Table className="mt-3">
      <TableBody>
        {shown.map(([label, value, icon]) => (
          <TableRow key={label}>
            <TableCell className="w-28 align-top font-medium text-end">{label}</TableCell>
            <TableCell className="whitespace-normal text-start text-sm text-muted-foreground">
              {Array.isArray(value)
                ? icon ? <Chips items={value} icon={icon} /> : value.filter((v) => v.trim()).join('; ')
                : value}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function NumberedList({ label, items }: { label: string; items: string[] }) {
  const shown = items.filter((item) => item.trim())
  if (shown.length === 0) return null
  return (
    <div>
      <p className="mt-5 text-start text-base leading-relaxed text-muted-foreground">{label}</p>
      <ol className="list-inside list-decimal space-y-2 text-start text-sm">
        {shown.map((item, index) => <li key={index}>{item.replace(/\.$/, '')}.</li>)}
      </ol>
    </div>
  )
}

function Heading({ label, aside }: { label: string; aside?: string }) {
  return (
    <div className="my-1 flex items-center justify-start gap-2.5">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
        {initialsFor(label)}
      </span>
      <p className="space-x-2 text-start text-base font-medium">
        <span>{label}</span>
        {aside && <span className="text-xs font-normal text-muted-foreground">{aside}</span>}
      </p>
    </div>
  )
}

export function SpecialistsPanel({ team }: { team: SpecialistDto[] }) {
  return (
    <Panel title="Meet Your Specialist Team">
      {team.map((specialist, index) => (
        <div key={specialist.name}>
          <div className="my-1 flex p-1">
            <div className={`size-10 shrink-0 overflow-hidden rounded-full border-3 ${SPECIALIST_BORDERS[index % SPECIALIST_BORDERS.length]}`}>
              <img src={AvatarImg[index % AvatarImg.length]} alt={specialist.name} className="size-full rounded-full object-cover" />
            </div>
            <div className="px-2 text-start">
              <p className="text-sm font-medium">{specialist.name}</p>
              <p className="text-sm font-medium text-muted-foreground">{specialist.role}</p>
              <p className="text-xs font-medium text-muted-foreground">{specialist.description}</p>
            </div>
          </div>
          {index < team.length - 1 && <hr className="w-full" />}
        </div>
      ))}
    </Panel>
  )
}

export function ProductDomainPanel({ text }: { text: string }) {
  return (
    <Panel title="Product Domain Understanding">
      <Prose text={text} />
    </Panel>
  )
}

function pricingLine(tier: NonNullable<MarketDataDto['pricing']>[number]): string {
  const price = [tier.monthly_sub && `${tier.monthly_sub}/mo`, tier.yearly_sub && `${tier.yearly_sub}/yr`].filter(Boolean).join(', ')
  return price ? `${tier.tier}: ${price}` : tier.tier
}

export function MarketPanel({ fit, data }: { fit: string | null; data: MarketDataDto }) {
  const pricing = (data.pricing ?? []).filter((tier) => tier.tier?.trim()).map(pricingLine)
  return (
    <Panel title="Product-Market Fit Understanding">
      <Prose text={fit} />
      <Fields
        rows={[
          ['Buyer', data.buyer_type?.toUpperCase()],
          ['Category', data.category],
          ['Audience', data.target_audience],
          ['Geo', data.target_geo, MapPin],
          ['Fit', data.market_fit],
          ['Reasoning', data.market_fit_reasoning],
          ['Demand', data.market_demand],
          ['Growth', data.growth_outlook === 'unclear' ? null : data.growth_outlook],
          ['Willingness to pay', data.willingness_to_pay],
          [data.pricing_source === 'market_suggestion' ? 'Suggested pricing' : 'Pricing', pricing],
          ['Channels', data.distribution_channels, Megaphone],
          ['Adoption barriers', data.adoption_barriers],
          ['Category norms', data.category_conventions],
        ]}
      />
    </Panel>
  )
}

export function CompetitionPanel({ swod, profile }: { swod: CompetitionDataDto; profile: IdealCompetitorProfileDto | null }) {
  return (
    <Panel title="Competition Landscape Understanding">
      {/* Archetypes, not companies: this stage names nobody by design; the
          competitor agent finds the real firms later. */}
      {profile && profile.archetypes.length > 0 && (
        <>
          <p className="my-2 text-start text-base leading-relaxed text-muted-foreground">Ideal Competitor Archetypes</p>
          <Prose text={profile.category_definition} />
          <Fields rows={[['Price anchor', profile.price_anchor_range]]} />
          {profile.archetypes.map((archetype, index) => (
            <div key={index} className="my-5">
              <Heading
                label={archetype.label}
                aside={`${archetype.geography_scope}${archetype.confidence === 'low' ? ' · speculative' : ''}`}
              />
              <Fields
                rows={[
                  ['Description', archetype.archetype_description],
                  ['Offering', archetype.typical_offering],
                  ['Serves', archetype.customer_profile],
                  ['Pricing', archetype.pricing_model],
                  // Weaknesses before advantages: they are this offer's openings.
                  ["Where it's exposed", archetype.likely_weaknesses],
                  ['Where to look', archetype.where_to_find_them],
                ]}
              />
            </div>
          ))}
        </>
      )}
      <NumberedList label="Strengths" items={swod.strengths} />
      <NumberedList label="Weaknesses" items={swod.weaknesses} />
      <NumberedList label="Opportunities" items={swod.opportunities} />
      <NumberedList label="Differentiators" items={swod.differentiators} />
    </Panel>
  )
}

export function IcpPanel({ data }: { data: IcpDto }) {
  const leads = data.competitor_leads.filter((lead) => lead.competitor_name?.trim())
  const personas = (data.buyer_personas ?? []).filter((persona) => persona.name?.trim())
  const channels = (data.target_channels ?? []).filter((channel) => channel.name?.trim())
  return (
    <Panel title="Ideal Customer Profile">
      <Prose text={data.beachhead && `Beachhead: ${data.beachhead}`} />
      <Fields
        rows={[
          ['Buyer type', data.buyer_type?.toUpperCase(), BadgeCheck],
          ['Industries', data.industries, Factory],
          ['Company sizes', data.company_sizes, Building2],
          ['Target geo', data.geo, MapPin],
          ['Buyer titles', data.buyer_titles, UserStar],
          ['Pain signals', data.pain_signals],
          ['Intent keywords', data.intent_keywords, SearchCheck],
          ['Messaging angles', data.messaging_angles],
          ['Events', data.event_focus],
          ['Exclusions', data.exclusions, SearchX],
        ]}
      />
      {personas.length > 0 && <p className="mt-5 text-start text-base leading-relaxed text-muted-foreground">Buyer Personas</p>}
      {personas.map((persona) => (
        <div key={persona.name} className="my-4">
          <Heading label={persona.name} />
          <Fields rows={[['Who', persona.who], ['Where', persona.where_they_congregate, MapPin], ['In market when', persona.intent_signals]]} />
        </div>
      ))}
      {channels.length > 0 && <p className="mt-5 text-start text-base leading-relaxed text-muted-foreground">Where To Reach Them</p>}
      {channels.map((channel) => (
        <div key={channel.name} className="my-4">
          <Heading label={channel.name} aside={channel.channel_type.replace(/_/g, ' ')} />
          <Fields rows={[['Why', channel.audience_fit], ['First move', channel.first_angle, undefined]]} />
        </div>
      ))}
      {leads.length > 0 && <p className="mt-5 text-start text-base leading-relaxed text-muted-foreground">Competitor Leads</p>}
      {leads.map((lead) => (
        <div key={lead.competitor_name} className="my-5">
          <Heading label={lead.competitor_name} />
          <Fields rows={[['Search queries', lead.search_queries, Search], ['Pain angles', lead.pain_angles, CheckCheck]]} />
        </div>
      ))}
      {!leads.length && !personas.length && !channels.length && !present(data.industries) && !present(data.buyer_titles) && (
        <p className="text-start text-sm text-muted-foreground">
          <Target className="mr-1 inline size-3.5" />
          No profile details came back for this stage.
        </p>
      )}
    </Panel>
  )
}
