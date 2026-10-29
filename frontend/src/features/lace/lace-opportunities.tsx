import { ExternalLink, Loader2, MessageCircle, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { LaceOpportunityDto, OpportunityKind } from "@/lib/api"

import type { LaceOpportunities as Opportunities } from "./use-lace-opportunities"
import { ITEM_CARD } from "./feed-styles"

const KINDS: { id: OpportunityKind; label: string }[] = [
  { id: "sell", label: "Sell" },
  { id: "showcase", label: "Showcase" },
  { id: "partner", label: "Partner" },
  { id: "funding", label: "Funding" },
]

function when(deadline: string | null, eventDate: string | null): string | null {
  const day = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
  if (deadline) return `Closes ${day(deadline)}`
  if (eventDate) return day(eventDate)
  return null
}

/** Events to showcase at, tenders and buyers to sell to, partners, funding: the saved
 * ones still open, the soonest first, each with a way to talk it through
 * with the Lace. Dismissing one drops it for good. */
export function LaceOpportunities({ opps, searching, name, onDiscuss }: {
  opps: Opportunities
  searching: boolean
  name: string
  onDiscuss: (opportunity: LaceOpportunityDto) => void
}) {
  const { opportunities, loading, error, dismiss } = opps
  if (loading) return <Skeleton className="h-24 w-full" />
  return (
    <div className="flex flex-col gap-6">
      {searching && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Loader2 className="size-4 animate-spin" /> Looking for opportunities. This takes a few minutes.
        </p>
      )}
      {opportunities.length === 0 && !searching && (
        <p className="text-sm text-muted-foreground">
          None saved yet. Ask your Lace to look for opportunities; it also looks on its own, as often as its settings say.
        </p>
      )}
      {KINDS.map((kind) => {
        const items = opportunities.filter((o) => o.kind === kind.id)
        if (items.length === 0) return null
        return (
          <section key={kind.id} className="flex flex-col gap-3">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{kind.label}</h3>
            <ul className="flex flex-col gap-3">
              {items.map((o) => {
                const date = when(o.deadline, o.event_date)
                return (
                  <li key={o.id} className={`${ITEM_CARD} flex items-start justify-between gap-3`}>
                    <div className="flex min-w-0 flex-col gap-1">
                      <a href={o.url} target="_blank" rel="noreferrer" className="inline-flex items-start gap-1 font-medium hover:underline">
                        {o.title} <ExternalLink className="mt-1 size-3 shrink-0" />
                      </a>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        {date && <Badge variant={o.deadline ? "default" : "secondary"}>{date}</Badge>}
                        {o.organiser && <span>{o.organiser}</span>}
                        {o.location && <span>{o.location}</span>}
                      </div>
                      <p className="text-sm">{o.why_it_fits}</p>
                      <p className="text-sm text-muted-foreground">Next: {o.how_to_act}</p>
                      <Button size="sm" variant="outline" className="mt-1 w-fit rounded-full border-theme/40 hover:bg-theme/10"
                              onClick={() => onDiscuss(o)}>
                        <MessageCircle /> Discuss with {name}
                      </Button>
                    </div>
                    <Button variant="ghost" size="icon" aria-label={`Dismiss ${o.title}`} title="Not for us"
                            onClick={() => void dismiss(o.id)}>
                      <X />
                    </Button>
                  </li>
                )
              })}
            </ul>
          </section>
        )
      })}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
  )
}
