import { useEffect, useState } from "react"

import { listLaceMoves, type LaceMoveDto } from "@/lib/api"

/** A Lace's competitor moves by competitor, newest first. Refetched when
 * `refreshKey` changes (a check finished). A failure leaves them empty: the
 * competitors still show. */
export function useLaceMoves(laceId: string, refreshKey: string): ReadonlyMap<string, LaceMoveDto[]> {
  const [moves, setMoves] = useState<LaceMoveDto[]>([])

  useEffect(() => {
    let cancelled = false
    listLaceMoves(laceId)
      .then((next) => !cancelled && setMoves(next))
      .catch(() => undefined) // the competitors are still worth showing without their moves
    return () => { cancelled = true }
  }, [laceId, refreshKey])

  const byCompetitor = new Map<string, LaceMoveDto[]>()
  for (const move of moves) byCompetitor.set(move.competitor_id, [...(byCompetitor.get(move.competitor_id) ?? []), move])
  return byCompetitor
}
