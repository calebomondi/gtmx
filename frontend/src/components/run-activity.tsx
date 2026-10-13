import { useEffect, useState } from 'react'

import { useRunSteps } from '@/lib/use-run-steps'
import { cn } from '@/lib/utils'

const VISIBLE_STEPS = 5

function elapsed(since: string | null, now: number): string | null {
  if (!since) return null
  const seconds = Math.max(0, Math.floor((now - new Date(since).getTime()) / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** What a long agent run is doing right now: its latest steps, the time it has
 * taken, and how long such runs usually take, so a quiet minute doesn't look
 * like a broken page. */
export function RunActivity({
  runId,
  live,
  startedAt,
  typical,
}: {
  runId: string
  live: boolean
  startedAt: string | null
  /** e.g. "3–5 minutes" */
  typical: string
}) {
  const steps = useRunSteps(runId, live)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!live) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [live])

  const recent = steps.slice(-VISIBLE_STEPS)
  const took = elapsed(startedAt, now)

  return (
    <div className="flex flex-col gap-1.5">
      {recent.length > 0 && (
        <ol className="flex flex-col gap-1" aria-live="polite">
          {recent.map((step, i) => (
            <li
              key={step.id}
              className={cn(
                'truncate text-xs',
                i === recent.length - 1 ? 'text-foreground' : 'text-muted-foreground/70',
              )}
            >
              {step.text}
            </li>
          ))}
        </ol>
      )}
      {live && (
        <p className="text-[11px] text-muted-foreground">
          {took ? `${took} elapsed · ` : ''}usually {typical}. It keeps running if you leave this page.
        </p>
      )}
    </div>
  )
}
