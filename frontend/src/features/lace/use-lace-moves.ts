import { useEffect, useState } from "react"

import { listLaceMoves, type LaceMoveDto } from "@/lib/api"

/** A Lace's competitor moves, newest first. Refetched when `refreshKey`
 * changes (a check finished). A failure leaves them empty: the competitors
 * still show. */
export function useLaceMoves(laceId: string, refreshKey: string): LaceMoveDto[] {
  const [moves, setMoves] = useState<LaceMoveDto[]>([])

  useEffect(() => {
    let cancelled = false
    listLaceMoves(laceId)
      .then((next) => !cancelled && setMoves(next))
      .catch(() => undefined) // the competitors are still worth showing without their moves
    return () => { cancelled = true }
  }, [laceId, refreshKey])

  return moves
}
