import { motion } from "motion/react"

import type { RunDto } from "@/lib/api"

import { elapsed, jobLabel, useNow } from "./background-jobs"

/** What the Lace is doing in the background, above the chat's input: one
 * pill per running job (a search, drafting) with a beacon, how long it has
 * run, and a light sweeping across it. Nothing when nothing runs. */
export function LaceBackgroundWork({ name, jobs }: { name: string; jobs: RunDto[] }) {
  const now = useNow(jobs.length > 0)
  if (jobs.length === 0) return null
  return (
    <div role="status" aria-label={`${name} is working in the background`} className="flex w-full max-w-3xl flex-wrap gap-1.5">
      {jobs.map((job) => (
        <div key={job.id}
             className="relative flex items-center gap-2 overflow-hidden rounded-full border border-theme/30 bg-theme/5 px-3 py-1 text-xs">
          <span aria-hidden className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-theme opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-theme" />
          </span>
          <span>{jobLabel(job.kind)}</span>
          <span className="text-muted-foreground tabular-nums">{elapsed(job.started_at ?? job.created_at, now)}</span>
          <motion.span aria-hidden
                       className="pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-theme/20 to-transparent"
                       initial={{ x: "-100%" }} animate={{ x: "300%" }}
                       transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }} />
        </div>
      ))}
    </div>
  )
}
