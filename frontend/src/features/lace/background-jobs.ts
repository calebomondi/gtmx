import { useEffect, useState } from "react"

import type { FoundSection } from "./found-model"

/** What each background job is doing, said to the founder, and which kind
 * of find it fills (its chip in the dock spins while it runs). */
export const JOB_INFO: Record<string, { label: string; fills: FoundSection["key"] | null }> = {
  lace_competitors: { label: "Searching for competitors", fills: "competitors" },
  lace_monitor: { label: "Checking competitors for moves", fills: "competitors" },
  lace_icp: { label: "Working out your ideal customer", fills: "leads" },
  lace_accounts: { label: "Searching for leads", fills: "leads" },
  lace_contacts: { label: "Finding people to contact", fills: "contacts" },
  lace_opportunities: { label: "Looking for opportunities", fills: "opportunities" },
  lace_drafts: { label: "Drafting messages", fills: null },
  lace_reply: { label: "Reading replies", fills: null },
  lace_comments: { label: "Reading your TikTok comments", fills: null },
}

export function jobLabel(kind: string): string {
  return JOB_INFO[kind]?.label ?? "Working in the background"
}

/** "12s", "3m", "1h 5m": how long something has been running. */
export function elapsed(sinceIso: string, now: number): string {
  const s = Math.max(0, Math.floor((now - Date.parse(sinceIso)) / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${m % 60}m`
}

/** The time, ticking every `everyMs` while `active`. */
export function useNow(active: boolean, everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setNow(Date.now()), everyMs)
    return () => clearInterval(timer)
  }, [active, everyMs])
  return now
}
