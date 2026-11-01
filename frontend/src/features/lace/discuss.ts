import type { LaceAccountDto, LaceBriefDto, LaceCompetitorDto, LaceOpportunityDto, LaceRegulationDto } from "@/lib/api"

/** What opening the chat with a topic carries: the message waiting in the
 * input, for the founder to edit or send. */
export interface DiscussState {
  prefill: string
}

function day(iso: string): string {
  return new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
    .toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
}

/** A message that starts a conversation about one opportunity. */
export function discussOpportunity(o: LaceOpportunityDto): string {
  const details = [o.organiser, o.location, o.deadline ? `closes ${day(o.deadline)}` : o.event_date ? day(o.event_date) : null]
    .filter(Boolean).join(", ")
  return `Let's talk about this opportunity: "${o.title}"${details ? ` (${details})` : ""}. ${o.url}\n`
    + "How well does it fit us, is it worth our time, and how should we go about it?"
}

/** A message that starts a conversation about one lead. */
export function discussAccount(a: LaceAccountDto): string {
  const where = [a.geo, a.website].filter(Boolean).join(", ")
  const why = a.trigger ? ` They ${a.trigger.event.charAt(0).toLowerCase()}${a.trigger.event.slice(1)}.` : ""
  return `Let's talk about ${a.name}${where ? ` (${where})` : ""} as a lead.${why}\n`
    + "How strong a fit are they really, who should we reach there, and what should our first message lead with?"
}

/** A message that starts a conversation about one competitor. */
export function discussCompetitor(c: LaceCompetitorDto): string {
  return `Let's talk about ${c.name} (${c.website}) as a competitor.\n`
    + "Where do they beat us, where do we beat them, and how should we position against them?"
}

/** A message that starts a conversation about one competitor's move. */
export function discussMove(competitor: string, title: string, detectedAt: string, sources: string[]): string {
  const where = sources.length ? ` ${sources.join(" ")}` : ""
  return `Let's talk about ${competitor}'s move: "${title}" (${day(detectedAt)}).${where}\n`
    + "What does it mean for our offer and our customers, and what should we do about it?"
}

/** A message that starts a conversation about the latest brief. */
export function discussBrief(brief: LaceBriefDto): string {
  return `Let's go over your brief from ${day(brief.posted_at ?? brief.created_at)}.\n`
    + "What should we act on first, and what can wait?"
}

/** A message that starts a conversation about one law, regulation, bill or filing obligation. */
export function discussRegulation(r: LaceRegulationDto): string {
  const due = r.next_date ? ` (next date ${day(r.next_date)})` : ""
  return `Let's talk about "${r.title}"${due}. ${r.url}\n`
    + "What does it mean for us, what do we need to do, and by when?"
}
