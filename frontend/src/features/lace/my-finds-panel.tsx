import { useState } from "react"
import { ChevronDown, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { FindDto, FindKind } from "@/lib/api"
import { cn } from "@/lib/utils"

import { FindEditDialog } from "./find-edit-dialog"
import { MyFindRow } from "./my-find-row"
import type { MyFinds } from "./use-lace-finds"

/** The panel's tabs, named like the Feed's. */
const TABS: readonly { kind: FindKind; title: string }[] = [
  { kind: "competitor", title: "Competitors" },
  { kind: "account", title: "Leads" },
  { kind: "opportunity", title: "Opportunities" },
]

/** In the founder's private chat: what it found, theirs until they push it
 * to the team, by kind. Each can be ticked to go, noted for the reviewer,
 * edited or removed; ones waiting for review, and ones sent back (with
 * why), say so. */
export function MyFindsPanel({ finds }: { finds: MyFinds }) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<FindKind>("competitor")
  // Unticked ones stay behind; everything not yet pushed goes by default.
  const [held, setHeld] = useState<ReadonlySet<string>>(new Set())
  const [pushing, setPushing] = useState(false)
  const [editing, setEditing] = useState<FindDto | null>(null)
  const items = finds.items ?? []
  if (items.length === 0) return null
  const ofKind = (kind: FindKind) => items.filter((f) => f.kind === kind)
  // The chosen tab, or the first with something in it once that one empties.
  const shown = ofKind(tab).length > 0 ? tab : (TABS.find((t) => ofKind(t.kind).length > 0)?.kind ?? tab)
  const going = items.filter((f) => !f.proposed_at && !held.has(f.id))
  const toggle = (id: string) => setHeld((prev) => {
    const next = new Set(prev)
    if (!next.delete(id)) next.add(id)
    return next
  })
  const push = async () => {
    setPushing(true)
    await finds.push(going)
    setPushing(false)
  }
  return (
    <Card size="sm" className="w-full max-w-(--breakpoint-md) gap-2">
      <div className="flex items-center justify-between gap-2 px-3">
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
                className="flex cursor-pointer items-center gap-1.5 text-sm font-medium">
          <ChevronDown className={cn("size-4 transition-transform", !open && "-rotate-90")} />
          Your finds <span className="text-xs font-normal text-muted-foreground tabular-nums">{items.length}</span>
        </button>
        <Button size="xs" disabled={going.length === 0 || pushing} onClick={() => void push()}>
          <Send /> {going.length === 0 ? "Nothing to push" : `Push ${going.length} to the team`}
        </Button>
      </div>
      {open && (
        <div className="flex flex-col gap-2 px-3">
          <Tabs value={shown} onValueChange={(next) => setTab(next as FindKind)}>
            <TabsList variant="line" aria-label="Kind of find">
              {TABS.map(({ kind, title }) => (
                <TabsTrigger key={kind} value={kind} disabled={ofKind(kind).length === 0} className="gap-1.5 text-xs">
                  {title} <span className="text-muted-foreground tabular-nums">{ofKind(kind).length}</span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <ul className="flex max-h-72 flex-col divide-y overflow-y-auto">
            {ofKind(shown).map((find) => (
              <MyFindRow key={find.id} find={find} ticked={!held.has(find.id)} onToggle={() => toggle(find.id)}
                         finds={finds} onEdit={() => setEditing(find)} />
            ))}
          </ul>
        </div>
      )}
      <FindEditDialog find={editing} onClose={() => setEditing(null)} finds={finds} />
    </Card>
  )
}
