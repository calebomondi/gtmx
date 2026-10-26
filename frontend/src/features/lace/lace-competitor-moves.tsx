import { useEffect, useState } from "react"
import { ExternalLink, Lightbulb, MessageCircle, Target } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { LaceMoveDto } from "@/lib/api"
import { cn } from "@/lib/utils"

import { byDay, dayLabel, timeOfDay } from "./activity-days"

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}

/** One move on the rail: the time, a node (filled for a high-stakes move,
 * glowing while new), and what happened, what it means and what to do. */
function Step({ move, fresh, last, name, onDiscuss }: {
  move: LaceMoveDto
  fresh: boolean
  last: boolean
  name: string
  onDiscuss: (move: LaceMoveDto) => void
}) {
  return (
    <li className="grid grid-cols-[4.25rem_1.25rem_1fr] gap-x-2">
      <time dateTime={move.detected_at} className="pt-0.5 text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums">
        {timeOfDay(move.detected_at)}
      </time>
      <div className="relative flex justify-center">
        <span aria-hidden className={cn("relative z-[1] mt-1 size-3 rounded-full border-2",
                                        move.importance === "high" ? "border-theme bg-theme" : "border-theme bg-background",
                                        fresh && "shadow-[0_0_10px] shadow-theme/60")} />
        {!last && <span aria-hidden className="absolute top-4 bottom-0 w-px bg-border" />}
      </div>
      <div className="flex min-w-0 flex-col gap-1.5 pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">{move.competitor_name}</span>
          <Badge variant="secondary" className="capitalize">{move.kind}</Badge>
          {fresh && <span className="rounded-full bg-theme px-1.5 text-[10px] font-medium text-neutral-900">new</span>}
        </div>
        <p className="text-sm font-medium break-words">{move.title}</p>
        <p className="text-sm text-muted-foreground">{move.summary}</p>
        {move.implication && (
          <p className="flex gap-2 text-sm"><Target className="mt-0.5 size-3.5 shrink-0 text-theme" />
            <span><span className="font-medium">For us: </span>{move.implication}</span></p>
        )}
        {move.counter_move && (
          <p className="flex gap-2 text-sm"><Lightbulb className="mt-0.5 size-3.5 shrink-0 text-theme" />
            <span><span className="font-medium">Our move: </span>{move.counter_move}</span></p>
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

/** Every move the tracked competitors made, as a stepper per day (newest
 * first) in a box that scrolls past a set height, with a filter per
 * competitor. Moves new since the founder last looked glow; looking counts
 * as seen, while they stay marked for this visit. */
export function CompetitorMovesStepper({ moves, competitor, onCompetitor, seenAt, onSeen, name, onDiscuss }: {
  /** Newest first. */
  moves: LaceMoveDto[]
  /** The competitor shown, or null for all. */
  competitor: string | null
  onCompetitor: (competitorId: string | null) => void
  seenAt: number
  onSeen: () => void
  name: string
  onDiscuss: (move: LaceMoveDto) => void
}) {
  // What was new on arrival stays marked; the visit itself counts as seen.
  const [since] = useState(seenAt)
  const fresh = moves.filter((m) => Date.parse(m.detected_at) > since).length
  const [hadNew] = useState(fresh > 0)
  useEffect(() => {
    if (hadNew) onSeen()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on arrival: `onSeen` is a fresh closure each render
  }, [hadNew])

  if (moves.length === 0) return null
  const competitors = [...new Map(moves.map((m) => [m.competitor_id, m.competitor_name])).entries()]
  const shown = competitor ? moves.filter((m) => m.competitor_id === competitor) : moves
  return (
    <section id="competitor-moves" aria-label="Competitor moves" className="mb-4 scroll-mt-20 overflow-hidden rounded-2xl border bg-card">
      <div className="flex flex-col gap-2 border-b px-4 py-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-medium">Competitor moves</h2>
          <span className="text-xs text-muted-foreground">
            {shown.length} {shown.length === 1 ? "move" : "moves"}{fresh > 0 && ` · ${fresh} new`}
          </span>
        </div>
        {competitors.length > 1 && (
          <div className="flex flex-wrap gap-1.5">
            {[[null, "All"] as const, ...competitors].map(([id, label]) => (
              <Button key={id ?? "all"} size="xs" variant={competitor === id ? "default" : "outline"}
                      className="rounded-full" aria-pressed={competitor === id} onClick={() => onCompetitor(id)}>
                {label}
              </Button>
            ))}
          </div>
        )}
      </div>
      <div className="max-h-[28rem] overflow-y-auto overscroll-contain">
        {byDay(shown, (m) => m.detected_at).map((group) => (
          <div key={group.day}>
            <h3 className="sticky top-0 z-[2] bg-card/95 px-4 py-2 text-xs font-medium text-muted-foreground backdrop-blur">
              {dayLabel(group.day)}
            </h3>
            <ol className="px-4 pt-1">
              {group.items.map((move, i) => (
                <Step key={move.id} move={move} fresh={Date.parse(move.detected_at) > since}
                      last={i === group.items.length - 1} name={name} onDiscuss={onDiscuss} />
              ))}
            </ol>
          </div>
        ))}
      </div>
    </section>
  )
}
