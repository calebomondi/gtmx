import { useEffect, useState } from "react"
import { ArrowLeft, Inbox, Loader2, Mail, Search } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group"
import type { LaceOutreachChanges, LaceOutreachDto, OutreachChannel } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

import { DraftCard } from "./lace-draft"
import { useScrollToEnd } from "./use-scroll-to-end"
import {
  answering,
  CHANNEL_LABELS,
  groupThreads,
  inFolder,
  initials,
  isUnread,
  matchesQuery,
  preview,
  type OutreachThread,
  type ThreadFolder,
} from "./outreach-threads"

const INTENT_LABELS: Record<string, string> = {
  interested: "Interested", question: "Asked a question", objection: "Raised an objection",
  meeting_request: "Wants to meet", not_now: "Not now", unsubscribe: "Asked to stop",
  out_of_office: "Out of office", referral: "Referred you on", other: "Replied",
}
const PROBLEMS: Partial<Record<LaceOutreachDto["status"], string>> = {
  sending: "Sending…", bounced: "Bounced: it never arrived.",
}
// lucide has no brand marks for most networks: a short wordmark instead.
const CHANNEL_MARKS: Record<Exclude<OutreachChannel, "email">, string> = {
  linkedin: "in", x: "X", instagram: "IG", facebook: "f", tiktok: "TT",
}

export interface ThreadActions {
  sendingSoon: ReadonlySet<string>
  onSave: (id: string, changes: LaceOutreachChanges) => void
  onDiscard: (id: string) => void
  onSend: (id: string) => void
  onUndo: (id: string) => void
  onMarkSent: (id: string) => void
  /** Replies the founder opened. */
  onRead: (ids: string[]) => void
}

/** The person's initials, with their channel's mark in the corner. */
function Avatar({ thread, size = "md" }: { thread: OutreachThread; size?: "md" | "lg" }) {
  return (
    <span className={cn("relative grid shrink-0 place-items-center rounded-full bg-theme/15 font-medium text-theme",
                        size === "lg" ? "size-10 text-sm" : "size-9 text-xs")}>
      {initials(thread.who)}
      <span className="absolute -right-1 -bottom-1 grid size-4 place-items-center rounded-full border bg-background text-[9px] font-semibold text-muted-foreground"
            title={CHANNEL_LABELS[thread.channel]}>
        {thread.channel === "email" ? <Mail className="size-2.5" /> : CHANNEL_MARKS[thread.channel]}
      </span>
    </span>
  )
}

export function Bubble({ message }: { message: LaceOutreachDto }) {
  const theirs = message.direction === "inbound"
  return (
    <div className={cn("flex flex-col gap-1", theirs ? "items-start" : "items-end")}>
      <div className={cn("max-w-[85%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap",
                         theirs ? "rounded-bl-sm bg-muted" : "rounded-br-sm bg-theme/15")}>
        {message.subject && !theirs && <p className="mb-1 font-medium">{message.subject}</p>}
        {message.body}
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {theirs && (
          <Badge variant={message.intent === "unsubscribe" ? "destructive" : "secondary"}>
            {message.intent ? INTENT_LABELS[message.intent] ?? message.intent : "Reading…"}
          </Badge>
        )}
        {PROBLEMS[message.status] && <span className={message.status === "bounced" ? "text-destructive" : ""}>{PROBLEMS[message.status]}</span>}
        <span>{formatRelativeTime(Date.parse(message.sent_at ?? message.created_at))}</span>
      </div>
    </div>
  )
}

/** One conversation, opened at its newest message. In Drafts it shows only
 * the drafts and the reply they answer; the whole history is under
 * Conversations. */
function ThreadView({ thread, folder, actions, onBack }: {
  thread: OutreachThread
  folder: ThreadFolder
  actions: ThreadActions
  onBack: () => void
}) {
  const drafts = thread.messages.filter((m) => m.direction === "outbound" && (m.status === "draft" || m.status === "failed"))
  const replyTo = folder === "drafts" ? answering(thread, drafts) : null
  const said = folder === "drafts" ? (replyTo ? [replyTo] : []) : thread.messages.filter((m) => !drafts.includes(m))
  const scroller = useScrollToEnd<HTMLDivElement>(thread.key, thread.messages.length)
  // Shown is read: its replies stop counting as new.
  const unread = thread.messages.filter(isUnread).map((m) => m.id).join(",")
  const { onRead } = actions
  useEffect(() => {
    if (unread) onRead(unread.split(","))
  }, [unread, onRead])
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <header className="flex items-center gap-3 border-b px-4 py-3">
        <Button size="icon-sm" variant="ghost" className="md:hidden" onClick={onBack} aria-label="All conversations">
          <ArrowLeft />
        </Button>
        <Avatar thread={thread} size="lg" />
        <div className="min-w-0">
          <p className="truncate font-medium">{thread.who}</p>
          <p className="truncate text-xs text-muted-foreground">
            {thread.company && thread.company !== thread.who ? `${thread.company} · ` : ""}{CHANNEL_LABELS[thread.channel]}
          </p>
        </div>
      </header>
      <div ref={scroller} className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        {replyTo && <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Answering</p>}
        {said.length > 0 && <div className="flex flex-col gap-3">{said.map((m) => <Bubble key={m.id} message={m} />)}</div>}
        {drafts.map((m) => (
          <DraftCard key={m.id} message={m} sendingSoon={actions.sendingSoon.has(m.id)}
                     onSave={(changes) => actions.onSave(m.id, changes)} onDiscard={() => actions.onDiscard(m.id)}
                     onSend={() => actions.onSend(m.id)} onUndo={() => actions.onUndo(m.id)}
                     onMarkSent={() => actions.onMarkSent(m.id)} />
        ))}
      </div>
    </div>
  )
}

function ThreadRow({ thread, selected, onSelect }: { thread: OutreachThread; selected: boolean; onSelect: () => void }) {
  return (
    <button type="button" onClick={onSelect} aria-current={selected ? "true" : undefined}
            className={cn("flex w-full cursor-pointer items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-muted/70",
                          selected && "md:bg-muted")}>
      <Avatar thread={thread} />
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-2">
          <span className={cn("truncate text-sm", thread.needsYou ? "font-semibold" : "font-medium")}>{thread.who}</span>
          <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{formatRelativeTime(Date.parse(thread.updatedAt))}</span>
        </span>
        {thread.company && thread.company !== thread.who && (
          <span className="truncate text-xs text-muted-foreground">{thread.company}</span>
        )}
        <span className="flex items-center gap-2">
          <span className="line-clamp-1 flex-1 text-xs text-muted-foreground">{preview(thread)}</span>
          {thread.needsYou && <span className="size-2 shrink-0 rounded-full bg-theme" aria-label="Needs you" />}
        </span>
      </span>
    </button>
  )
}

/** One folder of the Lace's conversations as an inbox: search over a list
 * (the ones that need the founder first), and the open conversation beside
 * it. On phones, one at a time. `empty` says what the folder holds when it
 * holds nothing. */
export function LaceThreads({ outreach, folder, drafting, actions, empty }: {
  outreach: LaceOutreachDto[]
  folder: ThreadFolder
  drafting: boolean
  actions: ThreadActions
  empty: { title: string; body: string }
}) {
  const threads = groupThreads(outreach).filter((t) => inFolder(t, folder))
  const [query, setQuery] = useState("")
  const [openKey, setOpenKey] = useState<string | null>(null)
  const shownThreads = threads.filter((t) => matchesQuery(t, query))
  // Phones show the list until a conversation is picked; wider screens
  // always show one, the first by default.
  const open = threads.find((t) => t.key === openKey) ?? null
  const shown = open ?? shownThreads[0] ?? null

  if (threads.length === 0) {
    const busy = drafting && folder === "drafts"
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed px-6 py-12 text-center">
        <span className="grid size-12 place-items-center rounded-full bg-theme/15 text-theme">
          {busy ? <Loader2 className="size-5 animate-spin" /> : <Inbox className="size-5" />}
        </span>
        <p className="font-medium">{busy ? "Drafting messages" : empty.title}</p>
        <p className="max-w-sm text-sm text-muted-foreground" aria-live="polite">
          {busy ? "This takes a few minutes. Each draft waits here for you to edit and send." : empty.body}
        </p>
      </div>
    )
  }
  return (
    <div className="grid h-[min(72svh,46rem)] overflow-hidden rounded-2xl border bg-card md:grid-cols-[19rem_1fr]">
      <div className={cn("flex min-h-0 flex-col md:border-r", open && "hidden md:flex")}>
        <div className="border-b p-3">
          <InputGroup>
            <InputGroupAddon><Search /></InputGroupAddon>
            <InputGroupInput value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by person, company or words"
                             aria-label="Search conversations" />
          </InputGroup>
        </div>
        <ul className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-2" aria-label="Conversations">
          {shownThreads.map((thread) => (
            <li key={thread.key}>
              <ThreadRow thread={thread} selected={thread === shown} onSelect={() => setOpenKey(thread.key)} />
            </li>
          ))}
          {shownThreads.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">Nothing here.</li>
          )}
          {drafting && folder === "drafts" && (
            <li className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground" aria-live="polite">
              <Loader2 className="size-3 animate-spin" /> Drafting more…
            </li>
          )}
        </ul>
      </div>
      <div className={cn("min-h-0 min-w-0 flex-col", open ? "flex" : "hidden md:flex")}>
        {shown ? (
          <ThreadView thread={shown} folder={folder} actions={actions} onBack={() => setOpenKey(null)} />
        ) : (
          <p className="m-auto text-sm text-muted-foreground">Pick a conversation.</p>
        )}
      </div>
    </div>
  )
}
