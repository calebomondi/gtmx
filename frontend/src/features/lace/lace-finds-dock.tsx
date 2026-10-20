import { AnimatePresence, motion } from "motion/react"
import { ArrowRight, Plus, Radar, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

import { isNewSince, type FoundSection } from "./found-model"

// Finds listed in a chip's card; the rest are one click away.
const SHOWN = 5

function Card({ section, since, name }: { section: FoundSection; since: number; name: string }) {
  const waiting = section.items.filter((i) => i.waiting).length
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="grid size-7 place-items-center rounded-full bg-theme/15 text-theme"><section.icon className="size-3.5" /></span>
        <span className="font-medium">{section.title}</span>
        <span className="text-xs text-muted-foreground tabular-nums">{section.items.length}</span>
        {waiting > 0 && (
          <span className="ml-auto rounded-full border border-theme/40 bg-theme/10 px-2 py-0.5 text-[11px]">
            {waiting} {section.waitingLabel}
          </span>
        )}
      </div>
      <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto">
        {section.items.slice(0, SHOWN).map((item) => {
          const fresh = isNewSince(item, since)
          return (
            <li key={item.id} className={cn("flex items-start gap-2 rounded-lg px-2 py-1.5", fresh && "bg-theme/10")}>
              <span aria-hidden className={cn("mt-1.5 size-1.5 shrink-0 rounded-full",
                                              fresh ? "bg-theme" : item.waiting ? "border border-theme" : "bg-muted-foreground/40")} />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm">{item.label}{fresh && <span className="ml-1.5 text-[10px] text-theme">new</span>}</span>
                {item.detail && <span className="line-clamp-1 text-xs text-muted-foreground">{item.detail}</span>}
              </span>
              {item.waiting && (
                <span className="flex shrink-0 gap-0.5">
                  <Button size="xs" onClick={() => section.keep(item.id)}>{section.keepLabel}</Button>
                  {section.drop && (
                    <Button size="icon-xs" variant="ghost" aria-label={`Dismiss ${item.label}`} onClick={() => section.drop?.(item.id)}>
                      <X />
                    </Button>
                  )}
                </span>
              )}
            </li>
          )
        })}
      </ul>
      <Button size="sm" variant="ghost" className="justify-between" onClick={section.open}>
        {section.items.length > SHOWN ? `All ${section.items.length} ${section.title.toLowerCase()}` : `Open ${section.title.toLowerCase()}`}
        <ArrowRight />
      </Button>
      <p className="sr-only">Found by {name}.</p>
    </div>
  )
}

function Chip({ section, since, name, busy, onAsk }: {
  section: FoundSection
  since: number
  name: string
  busy: boolean
  onAsk: (prompt: string) => void
}) {
  const count = section.items.length
  const fresh = section.items.filter((i) => isNewSince(i, since)).length
  const waiting = section.items.filter((i) => i.waiting).length
  if (count === 0) {
    // Nothing yet: the chip offers to start on it.
    return (
      <button type="button" disabled={busy} onClick={() => onAsk(section.ask)} title={`Ask ${name}: “${section.ask}”`}
              className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border border-dashed px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-theme/50 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50">
        <Plus className="size-3" /> {section.title}
      </button>
    )
  }
  return (
    <Popover>
      <PopoverTrigger render={
        <button type="button" aria-label={`${section.title}: ${count}${waiting ? `, ${waiting} ${section.waitingLabel}` : ""}${fresh ? `, ${fresh} new` : ""}`}
                className={cn("relative flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-xs transition-all hover:border-theme/60",
                              fresh > 0 && "border-theme/60 shadow-[0_0_14px_-2px] shadow-theme/60")} />
      }>
        <section.icon className={cn("size-3.5", fresh > 0 || waiting > 0 ? "text-theme" : "text-muted-foreground")} />
        <span>{section.title}</span>
        {/* Remounts when the count changes, so a new find pops in. */}
        <motion.span key={count} initial={{ scale: 1.6 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 400, damping: 15 }}
                     className="font-semibold tabular-nums">
          {count}
        </motion.span>
        {waiting > 0 && <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-theme" />}
        {/* "+1 competitor" rises out of the chip as a find arrives. */}
        <AnimatePresence>
          {fresh > 0 && (
            <motion.span key={fresh} aria-hidden initial={{ y: 0, opacity: 1 }} animate={{ y: -26, opacity: 0 }}
                         transition={{ duration: 1.8, ease: "easeOut" }}
                         className="pointer-events-none absolute -top-1 left-1/2 -translate-x-1/2 rounded-full bg-theme px-2 py-0.5 text-[10px] font-medium whitespace-nowrap text-neutral-900">
              +{fresh} {section.noun}
            </motion.span>
          )}
        </AnimatePresence>
      </PopoverTrigger>
      <PopoverContent side="top" sideOffset={10} className="w-80">
        <Card section={section} since={since} name={name} />
      </PopoverContent>
    </Popover>
  )
}

/** Above the chat's input: what the Lace has found as you talk, one chip per
 * kind. A chip pops and glows as finds arrive; it opens a card of the newest,
 * where suggestions are saved or dismissed and people approved in place. A
 * kind with nothing yet offers to ask the Lace for it. */
export function LaceFindsDock({ name, sections, since, busy, onAsk }: {
  name: string
  sections: FoundSection[]
  since: number
  busy: boolean
  onAsk: (prompt: string) => void
}) {
  return (
    <div role="toolbar" aria-label={`What ${name} has found`}
         className="flex w-full max-w-3xl flex-wrap items-center gap-1.5 pt-2">
      <span className="flex shrink-0 items-center gap-1 pr-1 text-xs text-muted-foreground">
        <Radar className="size-3.5" /> Found
      </span>
      {sections.map((section) => (
        <Chip key={section.key} section={section} since={since} name={name} busy={busy} onAsk={onAsk} />
      ))}
    </div>
  )
}
