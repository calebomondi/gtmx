import type { LaceAccountDto, LaceCompetitorDto, LaceOutreachDto } from "@/lib/api"

// How many suggestions sit above the chat input at once.
const SHOWN = 3

/** What the founder might ask next, from where the Lace's work stands: the
 * next step of the pipeline first, then standing questions. */
export function suggestions({ accounts, competitors, outreach, busy }: {
  accounts: LaceAccountDto[]
  competitors: LaceCompetitorDto[]
  outreach: LaceOutreachDto[]
  /** A search is already running: don't suggest starting one. */
  busy: boolean
}): string[] {
  const out: string[] = []
  const written = new Set(outreach.map((m) => m.account_id))
  if (!busy) {
    if (accounts.length === 0) out.push("Find target accounts for us")
    else if (accounts.some((a) => !a.contacts_checked_at)) out.push("Find who to contact at my accounts")
    else if (accounts.some((a) => a.contact_status === "person" && !written.has(a.id))) {
      out.push("Draft outreach to my best accounts")
    }
  }
  out.push(competitors.length === 0 ? "Who are my competitors?" : "Any competitor moves this week?")
  out.push("Find opportunities for us")
  out.push("What should I focus on this week?")
  return out.slice(0, SHOWN)
}
