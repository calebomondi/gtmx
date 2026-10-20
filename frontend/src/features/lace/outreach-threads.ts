import type { LaceOutreachDto, OutreachChannel } from "@/lib/api"

/** One conversation with one person on one channel: what was sent, what
 * came back, and any draft waiting to go. */
export interface OutreachThread {
  key: string
  channel: OutreachChannel
  /** Who it is with: their name, else their address. */
  who: string
  company: string
  /** Oldest first. */
  messages: LaceOutreachDto[]
  /** When it last moved. */
  updatedAt: string
  /** A draft to send, or a reply not yet read. */
  needsYou: boolean
}

export const CHANNEL_LABELS: Record<OutreachChannel, string> = {
  email: "Email", linkedin: "LinkedIn", x: "X", instagram: "Instagram", facebook: "Facebook", tiktok: "TikTok",
}

function when(m: LaceOutreachDto): string {
  return m.sent_at ?? m.created_at
}

function threadKey(m: LaceOutreachDto): string {
  // A first draft has no thread yet: it opens one with its recipient.
  return m.thread_id ?? `${m.channel}:${(m.recipient_address ?? m.recipient_company).toLowerCase()}`
}

/** A draft to review and send, or a reply the Lace has not read yet. */
export function waitsOnFounder(m: LaceOutreachDto): boolean {
  return (m.direction === "outbound" && m.status === "draft")
    || (m.direction === "inbound" && m.status === "received" && m.intent === null)
}

/** The Lace's outreach as conversations: ones that need the founder first,
 * then the most recently active. */
export function groupThreads(outreach: LaceOutreachDto[]): OutreachThread[] {
  const byKey = new Map<string, LaceOutreachDto[]>()
  for (const m of outreach) {
    const key = threadKey(m)
    byKey.set(key, [...(byKey.get(key) ?? []), m])
  }
  const threads = [...byKey.entries()].map(([key, messages]) => {
    const sorted = [...messages].sort((a, b) => when(a).localeCompare(when(b)))
    // Name the thread after the person, wherever in it their name appears.
    const named = sorted.find((m) => m.recipient_name) ?? sorted[0]
    return {
      key,
      channel: sorted[0].channel,
      who: named.recipient_name ?? named.recipient_address ?? named.recipient_company,
      company: named.recipient_company,
      messages: sorted,
      updatedAt: when(sorted[sorted.length - 1]),
      needsYou: sorted.some(waitsOnFounder),
    }
  })
  return threads.sort((a, b) => Number(b.needsYou) - Number(a.needsYou) || b.updatedAt.localeCompare(a.updatedAt))
}

/** The line shown for a thread in the list: its latest message. */
export function preview(thread: OutreachThread): string {
  const last = thread.messages[thread.messages.length - 1]
  const prefix = last.status === "draft" ? "Draft: " : last.direction === "outbound" ? "You: " : ""
  return prefix + last.body.replace(/\s+/g, " ").trim()
}

/** The inbox's folders. */
export type ThreadFolder = "all" | "needs_you" | "drafts" | "sent" | "replies"

export const THREAD_FOLDERS: { value: ThreadFolder; label: string }[] = [
  { value: "all", label: "All" },
  { value: "needs_you", label: "Needs you" },
  { value: "drafts", label: "Drafts" },
  { value: "sent", label: "Sent" },
  { value: "replies", label: "Replies" },
]

export function inFolder(thread: OutreachThread, folder: ThreadFolder): boolean {
  switch (folder) {
    case "all": return true
    case "needs_you": return thread.needsYou
    case "drafts": return thread.messages.some((m) => m.direction === "outbound" && m.status === "draft")
    case "sent": return thread.messages.some((m) => m.status === "sent")
    case "replies": return thread.messages.some((m) => m.direction === "inbound")
  }
}

/** Threads whose person, company or messages mention `query`. */
export function matchesQuery(thread: OutreachThread, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  return [thread.who, thread.company, ...thread.messages.map((m) => `${m.subject ?? ""} ${m.body}`)]
    .some((text) => text.toLowerCase().includes(needle))
}

/** Up to two letters for a person's avatar. */
export function initials(name: string): string {
  const words = name.replace(/[^\p{L}\p{N} ]/gu, " ").trim().split(/\s+/).filter(Boolean)
  return (words.length > 1 ? words[0][0] + words[words.length - 1][0] : (words[0] ?? "?").slice(0, 2)).toUpperCase()
}

/** Counts for Messaging's header: drafts to send, replies, and messages sent. */
export function outreachTally(outreach: LaceOutreachDto[]): { drafts: number; replies: number; sent: number } {
  return {
    drafts: outreach.filter((m) => m.direction === "outbound" && m.status === "draft").length,
    replies: outreach.filter((m) => m.direction === "inbound").length,
    sent: outreach.filter((m) => m.status === "sent").length,
  }
}
