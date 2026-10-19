import { useState } from "react"
import { ArrowLeft, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { LaceOutreachChanges, LaceOutreachDto } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

import { DraftCard } from "./lace-draft"
import { CHANNEL_LABELS, groupThreads, preview, type OutreachThread } from "./outreach-threads"

const INTENT_LABELS: Record<string, string> = {
  interested: "Interested", question: "Asked a question", objection: "Raised an objection",
  meeting_request: "Wants to meet", not_now: "Not now", unsubscribe: "Asked to stop",
  out_of_office: "Out of office", referral: "Referred you on", other: "Replied",
}
const PROBLEMS: Partial<Record<LaceOutreachDto["status"], string>> = {
  sending: "Sending…", bounced: "Bounced: it never arrived.",
}

export interface ThreadActions {
  sendingSoon: ReadonlySet<string>
  onSave: (id: string, changes: LaceOutreachChanges) => void
  onDiscard: (id: string) => void
  onSend: (id: string) => void
  onUndo: (id: string) => void
  onMarkSent: (id: string) => void
}

function Bubble({ message }: { message: LaceOutreachDto }) {
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

function ThreadView({ thread, actions, onBack }: { thread: OutreachThread; actions: ThreadActions; onBack: () => void }) {
  const drafts = thread.messages.filter((m) => m.direction === "outbound" && (m.status === "draft" || m.status === "failed"))
  const said = thread.messages.filter((m) => !drafts.includes(m))
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex items-center gap-2">
        <Button size="icon-sm" variant="ghost" className="md:hidden" onClick={onBack} aria-label="All conversations">
          <ArrowLeft />
        </Button>
        <div className="min-w-0">
          <p className="truncate font-medium">{thread.who}</p>
          <p className="truncate text-xs text-muted-foreground">{thread.company} · {CHANNEL_LABELS[thread.channel]}</p>
        </div>
      </div>
      {said.length > 0 && <div className="flex flex-col gap-3">{said.map((m) => <Bubble key={m.id} message={m} />)}</div>}
      {drafts.map((m) => (
        <DraftCard key={m.id} message={m} sendingSoon={actions.sendingSoon.has(m.id)}
                   onSave={(changes) => actions.onSave(m.id, changes)} onDiscard={() => actions.onDiscard(m.id)}
                   onSend={() => actions.onSend(m.id)} onUndo={() => actions.onUndo(m.id)}
                   onMarkSent={() => actions.onMarkSent(m.id)} />
      ))}
    </div>
  )
}

/** Every conversation the Lace has drafted, sent or received, on every
 * channel: a list (the ones that need the founder first) and the one open.
 * On phones, one at a time. */
export function LaceThreads({ outreach, drafting, actions }: {
  outreach: LaceOutreachDto[]
  drafting: boolean
  actions: ThreadActions
}) {
  const threads = groupThreads(outreach)
  const [openKey, setOpenKey] = useState<string | null>(null)
  // Phones show the list until a conversation is picked; wider screens
  // always show one, the first by default.
  const open = threads.find((t) => t.key === openKey) ?? null
  const shown = open ?? threads[0]

  if (threads.length === 0) {
    return drafting ? (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
        <Loader2 className="size-4 animate-spin" /> Drafting messages. This takes a few minutes.
      </p>
    ) : (
      <p className="text-sm text-muted-foreground">No conversations yet. Ask your Lace to draft outreach to your accounts.</p>
    )
  }
  return (
    <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
      <ul className={cn("flex flex-col gap-1 md:border-r md:pr-3", open && "hidden md:flex")} aria-label="Conversations">
        {threads.map((thread) => (
          <li key={thread.key}>
            <button type="button" onClick={() => setOpenKey(thread.key)} aria-current={thread === shown ? "true" : undefined}
                    className={cn("flex w-full cursor-pointer flex-col gap-0.5 rounded-lg px-3 py-2 text-left hover:bg-muted",
                                  thread === shown && "md:bg-muted")}>
              <span className="flex items-center gap-2">
                {thread.needsYou && <span className="size-2 shrink-0 rounded-full bg-theme" aria-label="Needs you" />}
                <span className="truncate text-sm font-medium">{thread.who}</span>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">{formatRelativeTime(Date.parse(thread.updatedAt))}</span>
              </span>
              <span className="truncate text-xs text-muted-foreground">{thread.company} · {CHANNEL_LABELS[thread.channel]}</span>
              <span className="line-clamp-1 text-xs text-muted-foreground">{preview(thread)}</span>
            </button>
          </li>
        ))}
        {drafting && (
          <li className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground" aria-live="polite">
            <Loader2 className="size-3 animate-spin" /> Drafting more…
          </li>
        )}
      </ul>
      <div className={cn(!open && "hidden md:block")}>
        <ThreadView thread={shown} actions={actions} onBack={() => setOpenKey(null)} />
      </div>
    </div>
  )
}
