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

interface CompetitionData {
  competitors: Array<{
    name: string;
    description: string;
    website?: string | null;
    offering?: string | null;
    positioning?: string | null;
    comparison?: string | null;
  }>;
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  differentiators: string[];
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
      <p className="text-muted-foreground text-base leading-relaxed text-start my-2">Key Competitors</p>
      {data.competitors.map((competitor, index) => (
        <div key={index} className="my-5">
          <div className="flex gap-2.5 items-center justify-start my-1">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
              {initialsFor(competitor.name)}
            </span>
            <p className="text-start text-base font-medium space-x-2">
              <span>{competitor.name}</span>
              {competitor.website ? (
                <a
                  href={competitor.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-500 underline hover:text-blue-400"
                >
                  {competitor.website}
                </a>
              ) : (
                <span className="text-sm text-muted-foreground">Website unavailable</span>
              )}
            </p>
          </div>
          <Table className="mt-2">
            <TableBody>
              <TableRow>
                <TableCell className="font-medium text-end">Description</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start">{competitor.description}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium text-end">Positioning</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start">{competitor.positioning}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium text-end">Offering</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{competitor.offering}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium text-end">Comparison</TableCell>
                <TableCell className="whitespace-normal text-muted-foreground text-sm text-start ">{competitor.comparison}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      ))}
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Strengths</p>
      <ol className='list-inside list-decimal space-y-2 text-sm text-start'>
        {  
          data.strengths.map((strength) => (
            <li>{strength}.</li>
          ))
        }
      </ol>
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Weaknesses</p>
      <ol className='list-inside list-decimal space-y-2 text-sm text-start'>
        {  
          data.weaknesses.map((strength) => (
            <li>{strength}.</li>
          ))
        }
      </ol>
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Opportunities</p>
      <ol className='list-inside list-decimal space-y-2 text-sm text-start'>
        {  
          data.opportunities.map((strength) => (
            <li>{strength}.</li>
          ))
        }
      </ol>
      <p className="text-muted-foreground text-base leading-relaxed text-start mt-5">Differentiators</p>
      <ol className='list-inside list-decimal space-y-2 text-sm text-start'>
        {  
          data.differentiators.map((strength) => (
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
