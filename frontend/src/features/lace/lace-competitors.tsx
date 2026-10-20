import { ExternalLink, Loader2, MessageCircle, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { LaceCompetitorDto, LaceMoveDto } from "@/lib/api"

import { LaceCompetitorMoves } from "./lace-competitor-moves"
import { ITEM_CARD } from "./feed-styles"

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}

/** The companies the Lace tracks as competitors, each with the moves it made
 * (opened by themselves when some are new). Dismissing one stops tracking
 * it, and a later search won't bring it back. */
export function LaceCompetitors({ competitors, searching, onDismiss, moves, movesSeenAt, onMovesSeen, name, onDiscussMove,
                                  onDiscuss }: {
  competitors: LaceCompetitorDto[]
  searching: boolean
  onDismiss: (id: string) => void
  moves: ReadonlyMap<string, LaceMoveDto[]>
  movesSeenAt: (competitorId: string) => number
  onMovesSeen: (competitorId: string) => void
  name: string
  onDiscussMove: (move: LaceMoveDto) => void
  onDiscuss: (competitor: LaceCompetitorDto) => void
}) {
  return (
    <div className="flex flex-col gap-4">
      {searching && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Loader2 className="size-4 animate-spin" /> Searching for competitors. This takes a few minutes.
        </p>
      )}
      {competitors.length === 0 && !searching && (
        <p className="text-sm text-muted-foreground">None yet. Ask your Lace to find your competitors.</p>
      )}
      <ul className="flex flex-col gap-3">
        {competitors.map((c) => (
          <li key={c.id} className={`${ITEM_CARD} flex items-start justify-between gap-3`}>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{c.name}</span>
                {c.origin === "founder" && <Badge variant="secondary">Added by you</Badge>}
              </div>
              <a href={c.website} target="_blank" rel="noreferrer"
                 className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline">
                {host(c.website)} <ExternalLink className="size-3" />
              </a>
              {c.summary && <p className="mt-1 line-clamp-3 text-sm leading-snug">{c.summary}</p>}
              <Button size="sm" variant="outline" className="mt-2 w-fit rounded-full border-theme/40 hover:bg-theme/10"
                      onClick={() => onDiscuss(c)}>
                <MessageCircle /> Discuss with {name}
              </Button>
              <LaceCompetitorMoves moves={moves.get(c.id) ?? []} seenAt={movesSeenAt(c.id)}
                                   onSeen={() => onMovesSeen(c.id)} name={name} onDiscuss={onDiscussMove} />
            </div>
            <Button variant="ghost" size="icon" aria-label={`Stop tracking ${c.name}`} title="Not a competitor"
                    onClick={() => onDismiss(c.id)}>
              <X />
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}
