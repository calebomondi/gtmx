import { useEffect, type ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { BUYER_EXPLAINER, BUYER_LABEL, asBuyerType } from '@/lib/buyer-type'
import { ensureInsightsLoaded, useInsights } from '@/lib/insights-store'

import type { Signal } from './feed-types'
import { useSignalSubject } from './use-signal-subject'

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="text-sm leading-relaxed text-foreground">{children}</div>
    </div>
  )
}

function Pills({ items }: { items: string[] }) {
  if (items.length === 0) return <span className="text-muted-foreground">Not found yet</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <Badge key={item} variant="secondary" className="font-normal">{item}</Badge>
      ))}
    </div>
  )
}

/** "Discovery finished": the research it produced, at a glance. */
function DiscoverySummary({ workspaceId }: { workspaceId: string | undefined }) {
  useEffect(() => ensureInsightsLoaded(workspaceId), [workspaceId])
  const { insights } = useInsights(workspaceId)
  if (!insights) return null
  const buyer = asBuyerType(insights.market_data?.buyer_type ?? insights.icp?.buyer_type)
  const icp = insights.icp
  const sellsToCompanies = buyer !== 'b2c'
  const reachesPeople = buyer === 'b2c' || buyer === 'both'

  return (
    <>
      {insights.offer_snapshot?.offer_description && (
        <Section label="The offer">{insights.offer_snapshot.offer_description}</Section>
      )}
      {buyer && (
        <Section label="Who buys">
          <span className="font-medium">{BUYER_LABEL[buyer]}</span>
          <span className="text-muted-foreground"> · {BUYER_EXPLAINER[buyer]}</span>
        </Section>
      )}
      {insights.market_data?.market_fit && (
        <Section label="Market fit">
          <span className="font-medium capitalize">{insights.market_data.market_fit.replaceAll('_', ' ')}</span>
          {insights.market_data.market_fit_reasoning && (
            <span className="text-muted-foreground"> · {insights.market_data.market_fit_reasoning}</span>
          )}
        </Section>
      )}
      {icp && sellsToCompanies && (
        <Section label="Companies to target">
          <Pills items={[...icp.industries, ...icp.buyer_titles]} />
        </Section>
      )}
      {icp && reachesPeople && (
        <Section label="People and where to reach them">
          <Pills items={[...(icp.buyer_personas ?? []).map((p) => p.name), ...(icp.target_channels ?? []).map((c) => c.name)]} />
        </Section>
      )}
      {icp && icp.geo.length > 0 && <Section label="Countries"><Pills items={icp.geo} /></Section>}
      {(insights.ideal_competitor_profile?.archetypes.length ?? 0) > 0 && (
        <Section label="Kinds of competitor to watch">
          <Pills items={insights.ideal_competitor_profile?.archetypes.map((a) => a.label) ?? []} />
        </Section>
      )}
    </>
  )
}

/** The details a feed item stands for: the research behind "Discovery
 * finished", the competitor, or the target account, with the item's own
 * summary first. */
export function SignalDetailBody({ signal, workspaceId }: { signal: Signal; workspaceId: string | undefined }) {
  const subject = useSignalSubject(signal, workspaceId)
  const isDiscovery = signal.category === 'product' && signal.title === 'Discovery finished'

  return (
    <div className="flex flex-col gap-3">
      {signal.summary && !isDiscovery && <p className="text-sm leading-relaxed text-foreground">{signal.summary}</p>}
      {isDiscovery && <DiscoverySummary workspaceId={workspaceId} />}
      {subject.kind === 'competitor' && (
        <>
          {subject.competitor.positioning && <Section label="Positioning">{subject.competitor.positioning}</Section>}
          {subject.competitor.pricing && <Section label="Pricing">{subject.competitor.pricing}</Section>}
          {subject.competitor.weaknesses.length > 0 && (
            <Section label="Where they're weak">
              <ul className="list-disc pl-4">
                {subject.competitor.weaknesses.slice(0, 3).map((w) => <li key={w.text}>{w.text}</li>)}
              </ul>
            </Section>
          )}
        </>
      )}
      {subject.kind === 'account' && (
        <>
          {typeof subject.account.trigger_event?.event === 'string' && (
            <Section label="Why now">{subject.account.trigger_event.event}</Section>
          )}
          {subject.account.why_reach_out.length > 0 && (
            <Section label="Why reach out">
              <ul className="list-disc pl-4">
                {subject.account.why_reach_out.slice(0, 3).map((r) => <li key={r}>{r}</li>)}
              </ul>
            </Section>
          )}
          <Section label="Who to contact">
            <Pills items={subject.account.key_contacts
              .map((c) => [c.name, c.title].filter((v): v is string => typeof v === 'string' && Boolean(v)).join(', '))
              .filter(Boolean)} />
          </Section>
        </>
      )}
    </div>
  )
}
