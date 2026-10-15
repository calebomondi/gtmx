import { useEffect, type ReactNode } from 'react'
import { Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { AccountFit, AccountRecord, OutreachMessageDto } from '@/lib/api'
import { ensureInsightsLoaded, useInsights } from '@/lib/insights-store'

import { formatTimeAgo } from './feed-types'
import { useAccountFit } from './use-account-fit'

const STRENGTH_LABEL: Record<AccountFit['strength'], string> = {
  strong: 'Strong fit',
  moderate: 'Moderate fit',
  weak: 'Loose fit',
}

function Section({ label, aside, children }: { label: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
        {aside}
      </div>
      <div className="text-sm leading-relaxed text-foreground">{children}</div>
    </div>
  )
}

/** How the offer is named on the card: the company's name when known. */
function useOfferName(workspaceId: string | undefined): string {
  useEffect(() => ensureInsightsLoaded(workspaceId), [workspaceId])
  const { insights } = useInsights(workspaceId)
  const offer = insights?.offer_snapshot
  return offer?.company_name || offer?.offer_name || 'your offer'
}

function triggerText(account: AccountRecord): string | null {
  const event = account.trigger_event?.event
  return typeof event === 'string' && event ? event : null
}

function lastContact(messages: OutreachMessageDto[]): string {
  const last = [...messages].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0]
  const what = last.direction === 'inbound' ? 'they replied' : last.status === 'sent' ? 'you wrote' : `a message ${last.status}`
  const count = messages.length === 1 ? '1 message' : `${messages.length} messages`
  return `${count} so far · last ${formatTimeAgo(Date.parse(last.created_at))}, ${what}${last.subject ? `: “${last.subject}”` : ''}`
}

function FitSections({ fit, offerName }: { fit: AccountFit; offerName: string }) {
  return (
    <>
      <Section
        label={`How ${offerName} fits`}
        aside={<Badge variant="secondary" className="font-normal">{STRENGTH_LABEL[fit.strength]}</Badge>}
      >
        <p>{fit.need}</p>
        {fit.capability && <p className="mt-1 text-muted-foreground">Answered by: {fit.capability}</p>}
      </Section>
      {fit.payoff && (
        <Section
          label="What it's worth to them"
          aside={fit.benefit ? <Badge variant="outline" className="font-normal capitalize">{fit.benefit}</Badge> : undefined}
        >
          {fit.payoff}
        </Section>
      )}
      {fit.angle && <Section label="How to open">{fit.angle}</Section>}
    </>
  )
}

/** An opportunity: the account's trigger, why the offer suits it now, and
 * what has already been said to them. */
export function AccountOpportunity({
  workspaceId,
  account,
  messages,
}: {
  workspaceId: string | undefined
  account: AccountRecord
  messages: OutreachMessageDto[]
}) {
  const offerName = useOfferName(workspaceId)
  const fit = useAccountFit(workspaceId, account)
  const trigger = triggerText(account)

  return (
    <>
      {account.summary && <p className="text-sm leading-relaxed text-muted-foreground">{account.summary}</p>}
      {trigger && <Section label="The opportunity">{trigger}</Section>}
      {fit.status === 'ready' && <FitSections fit={fit.fit} offerName={offerName} />}
      {fit.status === 'assessing' && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" />
          Working out how {offerName} fits {account.name}…
        </p>
      )}
      {fit.status === 'unavailable' && (
        <p className="text-sm text-muted-foreground">The fit couldn't be assessed right now. Try again in a little while.</p>
      )}
      <Section label="Prior contact">
        {messages.length > 0 ? lastContact(messages) : 'None yet: the team can start fresh.'}
      </Section>
    </>
  )
}
