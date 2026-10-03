import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from '@/components/ui/table'
import { useEffect, type ReactNode } from 'react'
import { ArrowDown, BadgeCheck, Building2, CheckCheck, Factory, MapPin, Search, SearchCheck, SearchX, UserStar } from 'lucide-react'
import {
  SpecialistsSkeleton,
  ProductUnderstandSkeleton,
  MarketSkeleton,
  CompetitionSkeleton,
  IcpSkeleton,
} from '@/skeletons/index'
import { useAutoFollowScroll } from './use-auto-follow-scroll'
import type { PhaseResults, StepProgress } from '@/lib/agent-run-store'
import type { SpecialistDto } from '@/lib/api'
import { AvatarImg } from '@/components/specialist-avatargroup'

const SPECIALIST_BORDERS = [
  'border-red-500',
  'border-green-500',
  'border-blue-500',
  'border-amber-500',
]

function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

interface SpecialistData {
  name: string;
  role_title: string;
  focus: string;
  borderClass: string;
}

interface MarketData {
  buyer_type: string | null;
  category: string | null;
  target_audience: string | null;
  target_geo: string[];
  market_fit: string | null;
  market_fit_reasoning: string | null;
}

/** The competition stage's two outputs. `profile` is the primary one: the
 * archetype construct, which names no company by design. `swod` is the
 * offer-vs-standard judgment. `profile` is nullable because that stage
 * soft-fails its structured passes. */
interface CompetitionData {
  swod: {
    strengths: string[];
    weaknesses: string[];
    opportunities: string[];
    differentiators: string[];
  };
  profile: {
    category_definition: string;
    boundary_of_category: string[];
    archetypes: Array<{
      label: string;
      archetype_description: string;
      geography_scope: "local" | "regional" | "global" | "any";
      business_model?: string | null;
      typical_offering?: string | null;
      pricing_model?: string | null;
      customer_profile?: string | null;
      likely_advantages: string[];
      likely_weaknesses: string[];
      where_to_find_them: string[];
      confidence: "high" | "medium" | "low";
    }>;
    global_entry_signals: string[];
    local_defence_signals: string[];
    substitution_risks: string[];
    price_anchor_range?: string | null;
    channels: string[];
    confidence: "high" | "medium" | "low";
  } | null;
}

interface ICPData {
  product_name: string | null;
  buyer_type: string | null;
  industries: string[];
  company_sizes: string[];
  geo: string[];
  buyer_titles: string[];
  exclusions: string[];
  pain_signals: string[];
  intent_keywords: string[];
  competitor_leads: Array<{
    competitor_name: string;
    search_queries: string[];
    pain_angles: string[];
  }>;
}

const Specialists = (
  { data }: { data: SpecialistData[]}
) => {
  return (
    <div className="w-full max-w-md rounded-xl p-4">
      <div className="text-start mb-4">
        <p className="text-base font-medium">Meet Your Specialist Team</p>
      </div>
      {data.map((specialist, index) => (
        <div key={specialist.name}>
          <div className="my-1 flex p-1 last:mb-0">
            <div className={`h-10 w-10 shrink-0 overflow-hidden rounded-full border-3 ${specialist.borderClass}`}>
              <img
                src={AvatarImg[index % AvatarImg.length]}
                alt={specialist.name}
                className="h-full w-full rounded-full object-cover"
              />
            </div>
            <div className="px-2 text-start">
              <p className="text-sm font-medium">{specialist.name}</p>
              <p className="text-muted-foreground text-sm font-medium">{specialist.role_title}</p>
              <p className="text-muted-foreground text-xs font-medium">{specialist.focus}</p>
            </div>
          </div>
          {index < data.length - 1 && (
            <div className="grid place-items-center">
              <hr className="w-full" />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

const ProductDomain = (
  { data }: { data: string }
) => {
  return (
    <div className="w-full max-w-md rounded-xl p-4">
      <div className="mb-2 text-start">
        <p className="text-base font-medium">Product Domain Understanding</p>
      </div>
      <p className="text-muted-foreground text-sm leading-relaxed text-start">{data}</p>
    </div>
  )
}

const MarketFit = (
  { fit, data }: { fit: string, data: MarketData }
) => {
  return (
    <div className="w-full max-w-md rounded-xl p-4">
      <div className="mb-2 text-start">
        <p className="text-base font-medium">Product-Market Fit Understanding</p>
      </div>
      <p className="text-muted-foreground text-sm leading-relaxed text-start">{fit}</p>

      {data && (
        <Table className="mt-3">
          {/* <TableHeader>
            <TableRow>
              <TableHead className="w-24">Field</TableHead>
              <TableHead>Value</TableHead>
            </TableRow>
          </TableHeader> */}
          <TableBody>
            <TableRow>
              <TableCell className="font-medium text-end">Buyer</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start uppercase">{data.buyer_type}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Category</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start uppercase">{data.category}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Audience</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{data.target_audience}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Geo</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{data.target_geo.join(', ')}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Fit</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{data.market_fit}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Reasoning</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{data.market_fit_reasoning}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}
    </div>
  )
}

const Competition = (
  { data }: { data: CompetitionData }
) => {
  return (
    <div className="w-full max-w-md rounded-xl p-4">
      <div className="mb-2 text-start">
        <p className="text-base font-medium">Competition Landscape Understanding</p>
      </div>
      {/* ARCHETYPES, NOT COMPANIES. This stage names nobody by design --
          finding real rivals is a separate agent's job -- so what it has to show
          is the SHAPE of the threat it expects. Scope is deliberately prominent:
          a global or regional archetype is the interesting one, and if every row
          read "local" the geography filter would have crept back in. */}
      <p className="text-muted-foreground text-base leading-relaxed text-start my-2">
        {data.profile ? 'Ideal Competitor Archetypes' : 'Competitive profile unavailable'}
      </p>
      {data.profile?.category_definition ? (
        <p className="text-sm text-muted-foreground text-start mb-3 leading-relaxed">
          {data.profile.category_definition}
        </p>
      ) : null}
      {data.profile?.archetypes.map((archetype, index) => (
        <div key={index} className="my-5">
          <div className="flex gap-2.5 items-center justify-start my-1">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
              {initialsFor(archetype.label)}
            </span>
            <p className="text-start text-base font-medium space-x-2">
              <span>{archetype.label}</span>
              <span className="text-xs font-normal text-muted-foreground">
                {archetype.geography_scope}
                {archetype.confidence === 'low' ? ' · speculative' : ''}
              </span>
            </p>
          </div>
          <Table className="mt-2">
            <TableBody>
              <TableRow>
                <TableCell className="font-medium text-end">Description</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start">{archetype.archetype_description}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium text-end">Offering</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{archetype.typical_offering}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium text-end">Serves</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{archetype.customer_profile}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium text-end">Pricing</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{archetype.pricing_model}</TableCell>
              </TableRow>
              {/* Weaknesses first: they are the openings this offer has, and
                  burying them under a rival's advantages would invert the point. */}
              <TableRow>
                <TableCell className="font-medium text-end">Where it's exposed</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">
                  {archetype.likely_weaknesses.length > 0 ? archetype.likely_weaknesses.join('; ') : '—'}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium text-end">Where to look</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">
                  {archetype.where_to_find_them.length > 0 ? archetype.where_to_find_them.join('; ') : '—'}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      ))}
      {data.profile && data.profile.archetypes.length === 0 ? (
        <p className="text-sm text-muted-foreground text-start">
          No archetypes could be established from the research.
        </p>
      ) : null}
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Strengths</p>
      <ol className='list-inside list-decimal space-y-2 text-sm text-start'>
        {
          data.swod.strengths.map((strength) => (
            <li>{strength}.</li>
          ))
        }
      </ol>
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Weaknesses</p>
      <ol className='list-inside list-decimal space-y-2 text-sm text-start'>
        {
          data.swod.weaknesses.map((strength) => (
            <li>{strength}.</li>
          ))
        }
      </ol>
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Opportunities</p>
      <ol className='list-inside list-decimal space-y-2 text-sm text-start'>
        {
          data.swod.opportunities.map((strength) => (
            <li>{strength}.</li>
          ))
        }
      </ol>
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Differentiators</p>
      <ol className='list-inside list-decimal space-y-2 text-sm text-start'>
        {
          data.swod.differentiators.map((strength) => (
            <li>{strength}.</li>
          ))
        }
      </ol>
    </div>
  )
}

const IdealCustomer = (
  { data }: { data: ICPData }
) => {
  return (
    <div className="w-full max-w-md rounded-xl p-4">
      <div className="mb-2 text-start">
        <p className="text-base font-medium">Ideal Customer Profile</p>
      </div>
      {data && (
        <Table className="mt-3">
          {/* <TableHeader>
            <TableRow>
              <TableHead className="w-24">Field</TableHead>
              <TableHead>Value</TableHead>
            </TableRow>
          </TableHeader> */}
          <TableBody>
            <TableRow>
              <TableCell className="font-medium text-end">Buyer Type</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start uppercase">
                <div className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground">
                  <BadgeCheck className="h-3 w-3 text-blue-500" />
                  <div>{data.buyer_type}</div>
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Industries</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start">
                <div className="flex flex-wrap gap-2">
                  {data.industries.map((industry) => (
                    <div
                      key={industry}
                      className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                    >
                      <div className="h-full">
                        <Factory className="h-3 w-3 text-blue-500" />
                      </div>
                      <div>{industry}</div>
                    </div>
                  ))}
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Company Sizes</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">
                <div className="flex flex-wrap gap-2">
                  {data.company_sizes.map((size) => (
                    <div
                      key={size}
                      className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                    >
                      <div className="h-full">
                        <Building2 className="h-3 w-3 text-blue-500" />
                      </div>
                      <div>{size}</div>
                    </div>
                  ))}
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Target Geo</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">
                <div className="flex flex-wrap gap-2">
                  {data.geo.map((location) => (
                    <div
                      key={location}
                      className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                    >
                      <div className="h-full">
                        <MapPin className="h-3 w-3 text-blue-500" />
                      </div>
                      <div>{location}</div>
                    </div>
                  ))}
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Buyer Titles</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">
                <div className="flex flex-wrap gap-2">
                  {data.buyer_titles.map((title) => (
                    <div
                      key={title}
                      className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                    >
                      <div className="h-full">
                        <UserStar className="h-3 w-3 text-blue-500" />
                      </div>
                      <div>{title}</div>
                    </div>
                  ))}
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Exclusions</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">
                <div className="flex flex-wrap gap-2">
                  {data.exclusions.map((exclusion) => (
                    <div
                      key={exclusion}
                      className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                    >
                      <div className="h-full">
                        <SearchX className="h-3 w-3 text-blue-500" />
                      </div>
                      <div>{exclusion}</div>
                    </div>
                  ))}
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium text-end">Intent Keywords</TableCell>
              <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">
                <div className="flex flex-wrap gap-2">
                  {data.intent_keywords.map((keyword) => (
                    <div
                      key={keyword}
                      className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                    >
                      <div className="h-full">
                        <SearchCheck className="h-3 w-3 text-blue-500" />
                      </div>
                      <div>{keyword}</div>
                    </div>
                  ))}
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Competitor Leads</p>
      {data.competitor_leads.map((competitor, index) => (
        <div key={index} className="my-5">
          <div className="flex gap-2.5 items-center justify-start my-1">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
              {initialsFor(competitor.competitor_name)}
            </span>
            <p className="text-start text-base font-medium space-x-2">
              <span>{competitor.competitor_name}</span>
            </p>
          </div>
          <Table className="mt-2">
            <TableBody>
              <TableRow>
                <TableCell className="font-medium text-end">Search Queries</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start">
                  <div className="flex flex-wrap gap-2">
                    {competitor.search_queries.map((query) => (
                      <div
                        key={query}
                        className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                      >
                        <div className="h-full">
                          <Search className="h-3 w-3 text-blue-500" />
                        </div>
                        <div>{query}</div>
                      </div>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium text-end">Pain Angles</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start">
                  <div className="flex flex-wrap gap-2">
                    {competitor.pain_angles.map((painAngle) => (
                      <div
                        key={painAngle}
                        className="inline-flex items-center gap-1.5 rounded-full bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                      >
                        <div className="h-full">
                          <CheckCheck className="h-3.5 w-3.5 text-blue-500" />
                        </div>
                        <div>{painAngle}</div>
                      </div>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      ))}
    </div>
  )
}

function teamToSpecialists(team: SpecialistDto[]): SpecialistData[] {
  return team.map((member, index) => ({
    name: member.name,
    role_title: member.role,
    focus: member.description,
    borderClass: SPECIALIST_BORDERS[index % SPECIALIST_BORDERS.length],
  }))
}

export function ChainOfThoughtResultDispaly({
  progress,
  results,
}: {
  progress: StepProgress[]
  results?: PhaseResults
}) {
  const { containerRef, showScrollButton, updateScrollButton, scrollToBottom, followIfNear } = useAutoFollowScroll()

  useEffect(() => {
    followIfNear()
  }, [progress, followIfNear])

  const stepSections: { stepId: string; done: ReactNode; skeleton: ReactNode }[] = [
    {
      stepId: 'details1',
      done: results?.create_specialists ? (
        <Specialists data={teamToSpecialists(results.create_specialists)} />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <SpecialistsSkeleton />
        </div>
      ),
      skeleton: <SpecialistsSkeleton />,
    },
    {
      stepId: 'product',
      done: results?.understand_offer ? (
        <ProductDomain data={results.understand_offer} />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <ProductUnderstandSkeleton />
        </div>
      ),
      skeleton: <ProductUnderstandSkeleton />,
    },
    {
      stepId: 'market',
      done: results?.understand_market?.market_data ? (
        <MarketFit
          fit={
            results.understand_market.product_market_fit_understanding ?? '—'
          }
          data={results.understand_market.market_data}
        />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <MarketSkeleton />
        </div>
      ),
      skeleton: <MarketSkeleton />,
    },
    {
      stepId: 'competition',
      done: results?.understand_competition ? (
        <Competition data={results.understand_competition} />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <CompetitionSkeleton />
        </div>
      ),
      skeleton: <CompetitionSkeleton />,
    },
    {
      stepId: 'gtm',
      done: results?.determine_icp ? (
        <IdealCustomer data={results.determine_icp} />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <IcpSkeleton />
        </div>
      ),
      skeleton: <IcpSkeleton />,
    },
  ]

  const statusByStep = new Map(progress.map((entry) => [entry.stepId, entry.status]))

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        onScroll={updateScrollButton}
        className="grid h-full w-full min-h-0 place-items-center overflow-y-auto p-2"
      >
        <div className="w-full space-y-1">
          {stepSections.map((section) => {
            const status = statusByStep.get(section.stepId)

            if (status === 'done') {
              return <div key={section.stepId}>{section.done}</div>
            }

            if (status === 'running') {
              return (
                <div key={section.stepId} className="w-full max-w-md rounded-xl p-4">
                  {section.skeleton}
                </div>
              )
            }

            return null
          })}
        </div>
      </div>
      {showScrollButton && (
        <button
          type="button"
          onClick={scrollToBottom}
          aria-label="Scroll to bottom"
          title="Scroll to bottom"
          className="bg-background/95 text-foreground hover:bg-muted absolute right-4 bottom-4 z-10 inline-flex size-9 items-center justify-center rounded-full border shadow-md backdrop-blur-sm transition-colors"
        >
          <ArrowDown className="size-4" />
        </button>
      )}
    </div>
  )
}
