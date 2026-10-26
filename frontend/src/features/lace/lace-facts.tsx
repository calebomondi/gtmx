import { ExternalLink } from "lucide-react"

import type { FactDto, FactTopic } from "@/lib/api"
import { Badge } from "@/components/ui/badge"

const TOPIC_LABELS: Record<FactTopic, string> = {
  company: "Company",
  offer: "What it sells",
  pricing: "Pricing",
  customers: "Customers",
  market: "Market",
  competition: "Competition",
  icp: "Ideal customers",
  positioning: "Positioning",
}
const TOPIC_ORDER = Object.keys(TOPIC_LABELS) as FactTopic[]

function groupFacts(facts: FactDto[]): { topic: FactTopic; label: string; facts: FactDto[] }[] {
  return TOPIC_ORDER
    .map((topic) => ({ topic, label: TOPIC_LABELS[topic], facts: facts.filter((f) => f.topic === topic) }))
    .filter((group) => group.facts.length > 0)
}

function sourceLabel(url: string): string {
  try {
    const { hostname, pathname } = new URL(url)
    return hostname.replace(/^www\./, "") + (pathname === "/" ? "" : pathname)
  } catch {
    return url
  }
}

/** What the Lace knows about the startup, by topic, each with its source. */
export function LaceFacts({ facts }: { facts: FactDto[] }) {
  const groups = groupFacts(facts)
  if (groups.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing yet. Your Lace records what it learns here.</p>
  }
  return (
    <div className="flex flex-col gap-6">
      {groups.map((group) => (
        <section key={group.topic} className="flex flex-col gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{group.label}</h3>
          <ul className="flex flex-col gap-2">
            {group.facts.map((fact) => (
              <li key={fact.id} className="text-sm leading-snug">
                {fact.claim}
                <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {fact.origin === "user" ? (
                    <Badge variant="secondary">You told me</Badge>
                  ) : fact.source_url ? (
                    <a href={fact.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
                      {sourceLabel(fact.source_url)} <ExternalLink className="size-3" />
                    </a>
                  ) : null}
                  {fact.confidence === "low" && <Badge variant="outline">unsure</Badge>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
