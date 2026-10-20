import { ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { newestFirst, type FoundSection } from "./found-model"

// Items shown per section; the rest are a click away.
const SHOWN = 3

function Section({ section, since, onAsk, busy }: {
  section: FoundSection
  since: number
  onAsk: (prompt: string) => void
  busy: boolean
}) {
  const items = newestFirst(section.items)
  const fresh = items.filter((i) => Date.parse(i.at) > since).length
  return (
    <section className="flex flex-col gap-1.5">
      <button type="button" onClick={section.open}
              className="group flex cursor-pointer items-center gap-2 text-left text-sm font-medium">
        <section.icon className="size-4 text-theme" />
        {section.title}
        <span className="text-xs font-normal text-muted-foreground tabular-nums">{items.length}</span>
        {fresh > 0 && <span className="rounded-full bg-theme px-1.5 text-[10px] font-medium text-neutral-900">{fresh} new</span>}
        <ChevronRight className="ml-auto size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </button>
      {section.waiting > 0 && (
        <button type="button" onClick={section.open}
                className="w-fit cursor-pointer rounded-full border border-theme/40 bg-theme/10 px-2 py-0.5 text-[11px] hover:bg-theme/20">
          {section.waiting} {section.waitingLabel}
        </button>
      )}
      {items.length === 0 ? (
        <Button size="xs" variant="ghost" className="w-fit text-muted-foreground" disabled={busy} onClick={() => onAsk(section.ask)}>
          Ask: “{section.ask}”
        </Button>
      ) : (
        <ul className="flex flex-col gap-1">
          {items.slice(0, SHOWN).map((item) => {
            const isNew = Date.parse(item.at) > since
            return (
              <li key={item.id}
                  className={cn("flex items-start gap-2 rounded-md px-2 py-1 text-xs",
                                isNew ? "bg-theme/10 text-foreground" : "text-muted-foreground")}>
                <span aria-hidden className={cn("mt-1.5 size-1.5 shrink-0 rounded-full",
                                                isNew ? "bg-theme" : item.suggested ? "border border-theme" : "bg-muted-foreground/40")} />
                <span className="line-clamp-2">{item.label}</span>
              </li>
            )
          })}
          {items.length > SHOWN && (
            <li>
              <button type="button" onClick={section.open} className="cursor-pointer px-2 text-xs text-muted-foreground hover:text-foreground">
                and {items.length - SHOWN} more
              </button>
            </li>
          )}
        </ul>
      )}
    </section>
  )
}

/** Beside the chat: what the Lace has learned and found so far, so the
 * founder sees it collect things as they talk. Anything found since `since`
 * (when the Lace was opened) glows; each section opens where it lives, and
 * an empty one offers to ask the Lace for it. */
export function LaceFoundPanel({ name, sections, since, onAsk, busy, className }: {
  name: string
  sections: FoundSection[]
  since: number
  onAsk: (prompt: string) => void
  busy: boolean
  className?: string
}) {
  return (
    <aside aria-label={`What ${name} has found`} className={cn("flex flex-col gap-5", className)}>
      <div>
        <h2 className="text-sm font-medium">Found so far</h2>
        <p className="text-xs text-muted-foreground">What {name} collects as you talk. New finds glow.</p>
      </div>
      {sections.map((section) => (
        <Section key={section.key} section={section} since={since} onAsk={onAsk} busy={busy} />
      ))}
    </aside>
  )
}
