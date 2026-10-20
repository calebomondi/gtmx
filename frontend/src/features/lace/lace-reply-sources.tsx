import { useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { ExternalLink, Link2 } from "lucide-react"

import { cn } from "@/lib/utils"

import type { ReplySource } from "./reply-sources"

// Sites shown as letters on the closed button.
const MARKS = 3

/** Under a reply: a chain button showing how many sources it drew on (with
 * the first sites as letters), which unfolds the list. */
export function LaceReplySources({ sources }: { sources: ReplySource[] }) {
  const [open, setOpen] = useState(false)
  if (sources.length === 0) return null
  const hosts = [...new Set(sources.map((s) => s.host))]
  return (
    <div className="flex flex-col gap-2">
      <button type="button" onClick={() => setOpen((was) => !was)} aria-expanded={open}
              className={cn("flex w-fit cursor-pointer items-center gap-2 rounded-full border px-2.5 py-1 text-xs transition-colors",
                            open ? "border-theme/50 bg-theme/10 text-foreground" : "text-muted-foreground hover:border-theme/40 hover:text-foreground")}>
        <Link2 className="size-3.5" />
        {sources.length} {sources.length === 1 ? "source" : "sources"}
        <span aria-hidden className="flex -space-x-1.5">
          {hosts.slice(0, MARKS).map((h) => (
            <span key={h} className="grid size-4 place-items-center rounded-full border border-background bg-muted text-[9px] font-semibold uppercase">
              {h[0]}
            </span>
          ))}
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ol initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                     className="flex flex-col gap-1 overflow-hidden">
            {sources.map((s, i) => (
              <li key={`${s.url}:${i}`}>
                <a href={s.url} target="_blank" rel="noreferrer"
                   className="group flex items-center gap-2.5 rounded-lg border bg-card px-2.5 py-1.5 text-xs hover:border-theme/40">
                  <span className="grid size-5 shrink-0 place-items-center rounded-full bg-theme/15 text-[10px] font-semibold text-theme tabular-nums">
                    {s.n ?? i + 1}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-foreground">{s.label}</span>
                    <span className="truncate text-muted-foreground">{s.host}</span>
                  </span>
                  <ExternalLink className="size-3.5 shrink-0 text-muted-foreground group-hover:text-foreground" />
                </a>
              </li>
            ))}
          </motion.ol>
        )}
      </AnimatePresence>
    </div>
  )
}
