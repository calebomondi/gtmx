import { useState } from "react"
import { Check, Pencil, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { FactDto, FactTopic, FactVerdict } from "@/lib/api"

// The order the founder reads what was learned in, and each group's heading.
const GROUPS: { topic: FactTopic; title: string }[] = [
  { topic: "offer", title: "What you sell" },
  { topic: "customers", title: "Who buys" },
  { topic: "icp", title: "Who it's for" },
  { topic: "pricing", title: "Pricing" },
  { topic: "positioning", title: "How you stand out" },
  { topic: "company", title: "Your company" },
  { topic: "market", title: "Your market" },
  { topic: "competition", title: "Competition" },
]

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "") + new URL(url).pathname.replace(/\/$/, "")
  } catch {
    return url
  }
}

function FactRow({ fact, onReview, onCorrect }: {
  fact: FactDto
  onReview: (verdict: FactVerdict) => void
  onCorrect: (claim: string) => void
}) {
  const [draft, setDraft] = useState<string | null>(null)
  if (draft !== null) {
    return (
      <li className="flex flex-col gap-2 py-2">
        <Input value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Fact" autoFocus maxLength={500} />
        <div className="flex gap-2">
          <Button size="sm" disabled={!draft.trim()} onClick={() => { onCorrect(draft.trim()); setDraft(null) }}>Save</Button>
          <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>Cancel</Button>
        </div>
      </li>
    )
  }
  const confirmed = fact.confirmed_at !== null
  return (
    <li className="flex items-start gap-3 py-2">
      <div className="min-w-0 flex-1">
        <p className="text-sm">{fact.claim}</p>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {fact.source_url ? (
            <a href={fact.source_url} target="_blank" rel="noreferrer" className="hover:underline">{host(fact.source_url)}</a>
          ) : "Your words"}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {confirmed ? (
          <Badge variant="secondary"><Check /> Right</Badge>
        ) : (
          <Button size="icon-sm" variant="ghost" aria-label="That's right" title="That's right" onClick={() => onReview("confirmed")}>
            <Check />
          </Button>
        )}
        <Button size="icon-sm" variant="ghost" aria-label="Fix it" title="Fix it" onClick={() => setDraft(fact.claim)}>
          <Pencil />
        </Button>
        <Button size="icon-sm" variant="ghost" aria-label="That's wrong" title="That's wrong" onClick={() => onReview("retracted")}>
          <X />
        </Button>
      </div>
    </li>
  )
}

/** What a new Lace learned from the site, grouped by topic, for the founder
 * to confirm (✓), fix in their own words (✎) or strike out (✗). */
export function LaceFactReview({ facts, onReview, onCorrect }: {
  facts: FactDto[]
  onReview: (factId: string, verdict: FactVerdict) => void
  onCorrect: (factId: string, claim: string) => void
}) {
  const groups = GROUPS.map((g) => ({ ...g, facts: facts.filter((f) => f.topic === g.topic) }))
    .filter((g) => g.facts.length > 0)
  if (groups.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing left to review. You can tell your Lace more in the chat.</p>
  }
  return (
    <div className="flex flex-col gap-5">
      {groups.map((group) => (
        <section key={group.topic}>
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{group.title}</h3>
          <ul className="divide-y">
            {group.facts.map((fact) => (
              <FactRow key={fact.id} fact={fact} onReview={(verdict) => onReview(fact.id, verdict)}
                       onCorrect={(claim) => onCorrect(fact.id, claim)} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
