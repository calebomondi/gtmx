import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { ChevronDown, ExternalLink, Lightbulb, MessageCircle, Target } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { LaceMoveDto } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}

function Move({ move, fresh, name, onDiscuss }: {
  move: LaceMoveDto
  fresh: boolean
  name: string
  onDiscuss: (move: LaceMoveDto) => void
}) {
  return (
    <li className="relative pl-5">
      {/* A dot on the timeline: filled for a high-stakes move. */}
      <span aria-hidden className={cn("absolute top-1.5 left-0 size-2.5 rounded-full border-2",
                                      move.importance === "high" ? "border-theme bg-theme" : "border-theme/60 bg-background")} />
      <div className={cn("flex flex-col gap-1.5 rounded-lg p-2", fresh && "bg-theme/10")}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">{move.title}</span>
          <Badge variant="secondary" className="capitalize">{move.kind}</Badge>
          {fresh && <span className="rounded-full bg-theme px-1.5 text-[10px] font-medium text-neutral-900">new</span>}
          <span className="ml-auto text-xs text-muted-foreground">{formatRelativeTime(Date.parse(move.detected_at))}</span>
        </div>
        <p className="text-sm text-muted-foreground">{move.summary}</p>
        {move.implication && (
          <p className="flex gap-2 text-sm"><Target className="mt-0.5 size-3.5 shrink-0 text-theme" />
            <span><span className="font-medium">For you: </span>{move.implication}</span></p>
        )}
        {move.counter_move && (
          <p className="flex gap-2 text-sm"><Lightbulb className="mt-0.5 size-3.5 shrink-0 text-theme" />
            <span><span className="font-medium">Your move: </span>{move.counter_move}</span></p>
        )}
        <div className="flex flex-wrap items-center gap-1.5">
          {move.sources.map((url) => (
            <a key={url} href={url} target="_blank" rel="noreferrer"
               className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs text-muted-foreground hover:border-theme/40 hover:text-foreground">
              {host(url)} <ExternalLink className="size-3" />
            </a>
          ))}
          {move.sources.length === 0 && <span className="text-xs text-muted-foreground">No source page</span>}
          <Button size="xs" variant="ghost" className="ml-auto" onClick={() => onDiscuss(move)}>
            <MessageCircle /> Discuss with {name}
          </Button>
        </div>
      </div>
    </li>
  )
}

/** Under a competitor: the moves it made, newest first, folded until opened.
 * It opens by itself when some are new to the founder, and says how many. */
export function LaceCompetitorMoves({ moves, seenAt, onSeen, name, onDiscuss }: {
  moves: LaceMoveDto[]
  /** When the founder last opened this competitor's moves. */
  seenAt: number
  onSeen: () => void
  name: string
  onDiscuss: (move: LaceMoveDto) => void
}) {
  const fresh = moves.filter((m) => Date.parse(m.detected_at) > seenAt).length
  const [open, setOpen] = useState(fresh > 0)
  // What was new when they were opened stays marked while they are.
  const [since] = useState(seenAt)
  // Opened by itself for new moves: they count as seen from here on. Once,
  // on mount: `onSeen` is a fresh closure each render.
  const [openedForNew] = useState(fresh > 0)
  useEffect(() => {
    if (openedForNew) onSeen()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openedForNew])
  if (moves.length === 0) return <p className="mt-2 text-xs text-muted-foreground">No moves seen yet.</p>
  const toggle = () => {
    if (!open) onSeen()
    setOpen((was) => !was)
  }
  return (
    <div className="mt-2 flex flex-col gap-2">
      <button type="button" onClick={toggle} aria-expanded={open}
              className="flex w-fit cursor-pointer items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
        <ChevronDown className={cn("size-3.5 transition-transform", !open && "-rotate-90")} />
        {moves.length} {moves.length === 1 ? "move" : "moves"}
        {fresh > 0 && <span className="rounded-full bg-theme px-1.5 text-[10px] font-medium text-neutral-900">{fresh} new</span>}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ol initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                     className="relative ml-1 flex flex-col gap-2 overflow-hidden border-l border-theme/30 pb-1">
            {moves.map((move) => (
              <Move key={move.id} move={move} fresh={Date.parse(move.detected_at) > since} name={name} onDiscuss={onDiscuss} />
            ))}
          </motion.ol>
        )}
      </AnimatePresence>
    </div>
  )
}
