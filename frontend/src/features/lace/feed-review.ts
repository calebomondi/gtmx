import type { LaceAccountDto, LaceCompetitorDto, LaceOpportunityDto } from "@/lib/api"

/** One suggestion as the Feed's review list shows it. */
export interface ReviewItem {
  id: string
  title: string
  detail: string | null
  why: string | null
  url: string | null
}

export function competitorItem(c: LaceCompetitorDto): ReviewItem {
  return { id: c.id, title: c.name, detail: c.website, why: c.summary, url: c.website }
}

export function accountItem(a: LaceAccountDto): ReviewItem {
  const detail = [a.geo, a.case?.strength && `${a.case.strength} fit`].filter(Boolean).join(" · ") || null
  const why = [a.trigger?.event, a.case?.need && `Need: ${a.case.need}`].filter(Boolean).join(". ") || null
  return { id: a.id, title: a.name, detail, why, url: a.website }
}

export function opportunityItem(o: LaceOpportunityDto): ReviewItem {
  const when = o.deadline ? `closes ${o.deadline}` : o.event_date ? `on ${o.event_date}` : null
  return { id: o.id, title: o.title, detail: [o.kind, o.organiser, when].filter(Boolean).join(" · "), why: o.why_it_fits, url: o.url }
}
