import type { LaceAccountDto, LaceCompetitorDto, LaceOpportunityDto } from "@/lib/api"

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

/** A message that starts a conversation about one target customer. */
export function discussAccount(a: LaceAccountDto): string {
  const where = [a.geo, a.website].filter(Boolean).join(", ")
  const why = a.trigger ? ` They ${a.trigger.event.charAt(0).toLowerCase()}${a.trigger.event.slice(1)}.` : ""
  return `Let's talk about ${a.name}${where ? ` (${where})` : ""} as a customer.${why}\n`
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
