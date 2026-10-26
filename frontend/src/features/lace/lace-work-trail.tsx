import { useState } from "react"
import { Check, Loader2 } from "lucide-react"
import { motion } from "motion/react"

import { elapsed, useNow } from "./background-jobs"
import { LaceAvatar } from "./lace-avatar"

// Earlier steps kept in view; older ones fold away.
const SHOWN_STEPS = 4

/** While the Lace works on a turn: what it has done so far (ticked) and what
 * it is doing now, with how long the turn has taken. Mounted when the turn
 * starts, so its clock starts with it. */
export function LaceWorkTrail({ steps, fallback }: { steps: string[]; fallback: string }) {
  const [startedAt] = useState(() => new Date().toISOString())
  const now = useNow(true)
  const done = steps.slice(0, -1).slice(-SHOWN_STEPS)
  const current = steps[steps.length - 1] ?? fallback
  const hidden = Math.max(0, steps.length - 1 - SHOWN_STEPS)
  return (
    <div className="flex gap-3" aria-live="polite">
      <LaceAvatar animated />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5 pt-1 text-sm">
        {hidden > 0 && <span className="text-xs text-muted-foreground">{hidden} earlier steps</span>}
        {done.map((step, i) => (
          <motion.span key={`${i}:${step}`} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                       className="flex items-center gap-2 text-xs text-muted-foreground">
            <Check className="size-3.5 shrink-0 text-theme" /> <span className="truncate">{step}</span>
          </motion.span>
        ))}
        <motion.span key={current} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                     className="flex items-center gap-2">
          <Loader2 className="size-4 shrink-0 animate-spin text-theme" />
          <span className="truncate animate-pulse">{current}</span>
          <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{elapsed(startedAt, now)}</span>
        </motion.span>
      </div>
    </div>
  )
}
