import { ExternalLink, MessageCircle, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { BillStage, LaceRegulationDto, RegulationKind } from "@/lib/api"
import { countryName } from "@/lib/countries"

import { ITEM_CARD } from "./feed-styles"
import type { LaceRegulations } from "./use-lace-regulations"

const KINDS: { id: RegulationKind; label: string }[] = [
  { id: "bill", label: "Bills before parliament" },
  { id: "obligation", label: "Filing and registration" },
  { id: "law", label: "Laws" },
  { id: "regulation", label: "Regulations" },
]

const STAGES: Record<BillStage, string> = {
  published: "Published", first_reading: "First reading", committee: "In committee",
  second_reading: "Second reading", whole_house: "Committee of the whole House", third_reading: "Third reading",
  assented: "Signed into law", withdrawn: "Withdrawn", lapsed: "Lapsed",
}

function day(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
}

function Places({ codes }: { codes: string[] }) {
  return <>{codes.map(countryName).join(", ")}</>
}

/** The laws, regulations, bills and filing obligations the Lace tracks for
 * the startup, by kind, the soonest date first: a bill with where it stands,
 * each with why it applies, what to do, its source and a way to talk it
 * through. It is information with its source, not legal advice. */
export function LaceCompliance({ regulations, name, onDiscuss }: {
  regulations: LaceRegulations
  name: string
  onDiscuss: (regulation: LaceRegulationDto) => void
}) {
  const { jurisdiction, tracked, loading, error, dismiss } = regulations
  if (loading) return <Skeleton className="h-24 w-full" />
  const places = jurisdiction?.jurisdiction_confirmed_at
    ? [...new Set([jurisdiction.registered_in, ...jurisdiction.operates_in].filter((c): c is string => !!c))]
    : []
  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        {places.length > 0
          ? <>Watching the laws that apply in <Places codes={places} />. Change where you operate in {name}'s settings.</>
          : <>Confirm where you're registered and operate in {name}'s settings (or tell {name} in the chat), and it
              looks for the laws that apply there.</>}
      </p>
      {tracked.length === 0 && places.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Nothing tracked yet. Ask {name} what laws apply to us; it also looks on its own every week.
        </p>
      )}
      {KINDS.map((kind) => {
        const items = tracked.filter((r) => r.kind === kind.id)
        if (items.length === 0) return null
        return (
          <section key={kind.id} className="flex flex-col gap-3">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{kind.label}</h3>
            <ul className="flex flex-col gap-3">
              {items.map((r) => (
                <li key={r.id} className={`${ITEM_CARD} flex items-start justify-between gap-3`}>
                  <div className="flex min-w-0 flex-col gap-1">
                    <a href={r.url} target="_blank" rel="noreferrer" className="inline-flex items-start gap-1 font-medium hover:underline">
                      {r.title} <ExternalLink className="mt-1 size-3 shrink-0" />
                    </a>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      {r.stage && <Badge variant={r.stage === "assented" ? "default" : "secondary"}>{STAGES[r.stage]}</Badge>}
                      {r.next_date && <Badge>Next: {day(r.next_date)}</Badge>}
                      <span>{countryName(r.jurisdiction)}</span>
                      {r.authority && <span>{r.authority}</span>}
                    </div>
                    <p className="text-sm">{r.why_it_applies}</p>
                    {r.what_to_do && <p className="text-sm text-muted-foreground">To do: {r.what_to_do}</p>}
                    <Button size="sm" variant="outline" className="mt-1 w-fit rounded-full border-theme/40 hover:bg-theme/10"
                            onClick={() => onDiscuss(r)}>
                      <MessageCircle /> Discuss with {name}
                    </Button>
                  </div>
                  <Button variant="ghost" size="icon" aria-label={`Stop tracking ${r.title}`} title="Not for us"
                          onClick={() => void dismiss(r.id)}>
                    <X />
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
      <p className="text-xs text-muted-foreground">
        From official sources, each linked. It's information, not legal advice: check what to do with a lawyer or accountant.
      </p>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
  )
}
