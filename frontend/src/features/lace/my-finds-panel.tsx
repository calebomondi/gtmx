import { useState } from "react"
import { ChevronDown, Clock, Send, Undo2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import type { FindDto } from "@/lib/api"
import { cn } from "@/lib/utils"

import { FIND_KIND_LABEL, type MyFinds } from "./use-lace-finds"

/** In the founder's private chat: what it found, theirs until they push it
 * to the team. Each is ticked to go; ones waiting for review, and ones sent
 * back (with why), say so. */
export function MyFindsPanel({ finds }: { finds: MyFinds }) {
  const [open, setOpen] = useState(false)
  // Unticked ones stay behind; everything not yet pushed goes by default.
  const [held, setHeld] = useState<ReadonlySet<string>>(new Set())
  const [pushing, setPushing] = useState(false)
  const items = finds.items ?? []
  if (items.length === 0) return null
  const ready = items.filter((f) => !f.proposed_at)
  const going = ready.filter((f) => !held.has(f.id))
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
        <ul className="flex max-h-56 flex-col gap-1 overflow-y-auto px-3">
          {items.map((find) => (
            <FindRow key={find.id} find={find} ticked={!held.has(find.id)} onToggle={() => toggle(find.id)} />
          ))}
        </ul>
      )}
    </Card>
  )
}

function FindRow({ find, ticked, onToggle }: { find: FindDto; ticked: boolean; onToggle: () => void }) {
  const waiting = Boolean(find.proposed_at)
  return (
    <li className="flex items-start gap-2 py-1">
      <Checkbox checked={!waiting && ticked} disabled={waiting} onCheckedChange={onToggle} aria-label={`Push ${find.name}`}
                className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-sm">
          <span className="truncate">{find.name}</span>
          <Badge variant="outline" className="shrink-0 text-[10px]">{FIND_KIND_LABEL[find.kind]}</Badge>
        </p>
        {waiting && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground"><Clock className="size-3" /> Waiting for the team</p>
        )}
        {!waiting && find.review_note && (
          <p className="flex items-start gap-1 text-xs text-muted-foreground">
            <Undo2 className="mt-0.5 size-3 shrink-0" /> Sent back: {find.review_note}
          </p>
        )}
      </div>
    </li>
  )
}
