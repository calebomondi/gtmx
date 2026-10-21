import { useState } from "react"
import { ChevronDown, MessageCircle } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/ui/markdown"
import { Skeleton } from "@/components/ui/skeleton"
import type { LaceBriefDto } from "@/lib/api"
import { cn } from "@/lib/utils"

import { dayLabel, startOfDay } from "./activity-days"

function Writing({ name }: { name: string }) {
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <p className="text-sm text-muted-foreground">{name} is writing it now…</p>
      <Skeleton className="h-3 w-11/12" />
      <Skeleton className="h-3 w-4/5" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}

/** The Lace's latest brief at the top of its Feed: being written, or to read
 * in full right here (folded until opened), with a way to talk it over. */
export function LaceLatestBrief({ brief, name, onDiscuss }: {
  brief: LaceBriefDto | null
  name: string
  onDiscuss: () => void
}) {
  const [open, setOpen] = useState(false)
  if (!brief || brief.state === "missed") return null
  const day = dayLabel(startOfDay(new Date(brief.posted_at ?? brief.created_at)))
  return (
    <section aria-label="Latest brief"
             className="mb-4 flex flex-col gap-3 rounded-2xl border border-theme/40 bg-gradient-to-br from-theme/10 via-card to-card p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium">{name}'s brief</h2>
        <span className="text-xs text-muted-foreground">{day}</span>
      </div>
      {brief.state === "writing" || !brief.body ? <Writing name={name} /> : (
        <>
          <div className={cn("relative", !open && "max-h-40 overflow-hidden")}>
            <Markdown className="prose prose-sm dark:prose-invert min-w-0 max-w-none prose-p:my-1.5 prose-ul:my-1.5 prose-li:my-0.5">{brief.body}</Markdown>
            {!open && <div className="pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-card to-transparent" />}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="xs" variant="ghost" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
              <ChevronDown className={cn("transition-transform", open && "rotate-180")} /> {open ? "Fold" : "Read all"}
            </Button>
            <Button size="xs" variant="outline" className="rounded-full border-theme/40 hover:bg-theme/10" onClick={onDiscuss}>
              <MessageCircle /> Discuss with {name}
            </Button>
          </div>
        </>
      )}
    </section>
  )
}
