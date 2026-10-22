import { useEffect, useState } from "react"
import { Check, Copy, ExternalLink, Loader2, MessageCircleReply, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import type { ContactDto, LaceOutreachDto, OutreachChannel } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

import { ChannelIcon } from "./channel-icon"
import { messagesWith, reachOf, unreadByChannel, type Reach } from "./contacts-model"
import { DraftCard } from "./lace-draft"
import { Bubble } from "./lace-threads"
import { CHANNEL_LABELS, initials, isUnread } from "./outreach-threads"
import type { LaceChat } from "./use-lace-chat"
import { UnreadBadge } from "./unread-badge"
import { useScrollToEnd } from "./use-scroll-to-end"

const NOTE_IDEAS = ["Mention our pilot results", "Keep it under 80 words", "Ask for a 15-minute call"]

/** Their latest reply on a channel other than `channel`, if any. */
function replyElsewhere(messages: LaceOutreachDto[], channel: OutreachChannel): LaceOutreachDto | null {
  return messages.filter((m) => m.direction === "inbound" && m.channel !== channel).at(-1) ?? null
}

function CopyAddress({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button type="button" title={`Copy ${label}`}
            onClick={() => void navigator.clipboard.writeText(value).then(() => {
              setCopied(true)
              window.setTimeout(() => setCopied(false), 1500)
            })}
            className="grid size-6 cursor-pointer place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">
      {copied ? <Check className="size-3.5 text-theme" /> : <Copy className="size-3.5" />}
    </button>
  )
}

function AddressRow({ reach }: { reach: Reach }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border px-3 py-2 text-sm">
      <ChannelIcon channel={reach.channel} className="text-muted-foreground" />
      {reach.channel === "email" ? (
        <>
          <span className="min-w-0 flex-1 truncate">{reach.address}</span>
          <CopyAddress value={reach.address} label="email address" />
        </>
      ) : (
        <>
          <a href={reach.address} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate hover:underline">
            {reach.address.replace(/^https?:\/\/(www\.)?/, "")}
          </a>
          <ExternalLink className="size-3.5 text-muted-foreground" />
        </>
      )}
    </div>
  )
}

/** One person found at a saved account, one channel at a time: how to reach
 * them there, the conversation on it (drafts editable and sendable in
 * place), and a box to ask the Lace to write to them on it. Starting on a new
 * channel after they answered on another is allowed but discouraged. */
export function LaceContactDialog({ contact, channel: initialChannel, name, chat, onClose }: {
  contact: ContactDto
  channel: OutreachChannel | null
  name: string
  chat: LaceChat
  onClose: () => void
}) {
  const reach = reachOf(contact)
  const [channel, setChannel] = useState<OutreachChannel | null>(initialChannel ?? reach[0]?.channel ?? null)
  const [note, setNote] = useState("")
  const [asked, setAsked] = useState<OutreachChannel | null>(null)
  const [asking, setAsking] = useState(false)
  const everything = messagesWith(chat.outreach, contact)
  const messages = everything.filter((m) => m.channel === channel)
  const drafts = messages.filter((m) => m.direction === "outbound" && (m.status === "draft" || m.status === "failed"))
  const said = messages.filter((m) => !drafts.includes(m))
  const elsewhere = channel && messages.length === 0 ? replyElsewhere(everything, channel) : null
  const scroller = useScrollToEnd<HTMLDivElement>(channel ?? "", messages.length)
  const who = contact.name ?? contact.email ?? "this person"
  const current = reach.find((r) => r.channel === channel)
  const unreadOn = unreadByChannel(chat.outreach, contact)
  // The channel shown is read: its replies stop counting as new.
  const unread = messages.filter(isUnread).map((m) => m.id).join(",")
  const { markRead } = chat
  useEffect(() => {
    if (unread) markRead(unread.split(","))
  }, [unread, markRead])

  const pick = (next: OutreachChannel) => {
    setChannel(next)
    setAsked(null)
  }
  const ask = async () => {
    if (!channel) return
    setAsking(true)
    if (await chat.draftToContact(contact.id, channel, note)) setAsked(channel)
    setAsking(false)
  }
  const waiting = asked === channel && chat.drafting

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[88svh] gap-0 sm:max-w-xl">
        <div className="shrink-0 border-b">
          <DialogHeader className="flex-row items-center gap-3 space-y-0 pr-12">
            <span className="grid size-11 shrink-0 place-items-center rounded-full bg-theme/15 font-medium text-theme">
              {initials(who)}
            </span>
            <div className="min-w-0 text-left">
              <DialogTitle className="truncate">{who}</DialogTitle>
              <DialogDescription className="truncate">
                {[contact.title, contact.account_name].filter(Boolean).join(" · ")}
                {contact.approved_at ? " · approved for outreach" : ""}
              </DialogDescription>
            </div>
          </DialogHeader>
          {reach.length > 0 && (
            <div className="flex gap-1.5 overflow-x-auto px-4 pb-3 [scrollbar-width:none]" role="tablist" aria-label="Channel">
              {reach.map(({ channel: c }) => (
                <button key={c} type="button" role="tab" aria-selected={channel === c} onClick={() => pick(c)}
                        className={cn("flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors",
                                      channel === c ? "border-theme/60 bg-theme/15 text-foreground" : "text-muted-foreground hover:text-foreground")}>
                  <ChannelIcon channel={c} className="size-3.5" /> {CHANNEL_LABELS[c]}
                  {channel !== c && unreadOn[c] ? <UnreadBadge count={unreadOn[c]} /> : null}
                </button>
              ))}
            </div>
          )}
        </div>

        <div ref={scroller} className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
          {!current && <p className="text-sm text-muted-foreground">No email or social account on file for them.</p>}
          {current && <AddressRow reach={current} />}

          {current && (said.length > 0 || drafts.length > 0) && (
            <section className="flex flex-col gap-3">
              <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Your conversation on {CHANNEL_LABELS[current.channel]}
              </h3>
              {said.map((m) => <Bubble key={m.id} message={m} />)}
              {drafts.map((m) => (
                <DraftCard key={m.id} message={m} sendingSoon={chat.sendingSoon.has(m.id)}
                           onSave={(changes) => void chat.saveDraft(m.id, changes)} onDiscard={() => void chat.discardDraft(m.id)}
                           onSend={() => chat.sendDraft(m.id)} onUndo={() => chat.undoSend(m.id)}
                           onMarkSent={() => void chat.markSent(m.id)} />
              ))}
            </section>
          )}

          {current && elsewhere && (
            <div className="flex flex-col gap-2 rounded-xl border border-theme/40 bg-theme/10 p-3 text-sm" role="note">
              <p className="flex items-start gap-2">
                <MessageCircleReply className="mt-0.5 size-4 shrink-0 text-theme" />
                <span>
                  {who} replied to you by {CHANNEL_LABELS[elsewhere.channel]}{" "}
                  {formatRelativeTime(Date.parse(elsewhere.sent_at ?? elsewhere.created_at))}. Answering there keeps it one
                  conversation; starting a new one on {CHANNEL_LABELS[current.channel]} can read as ignoring their reply.
                </span>
              </p>
              <Button size="sm" variant="outline" className="self-start" onClick={() => pick(elsewhere.channel)}>
                <ChannelIcon channel={elsewhere.channel} className="size-3.5" /> Go to {CHANNEL_LABELS[elsewhere.channel]}
              </Button>
            </div>
          )}

          {current && (
            <section className="flex flex-col gap-3 rounded-xl border border-theme/30 bg-gradient-to-br from-theme/10 via-card to-card p-3">
              <h3 className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="size-4 text-theme" /> Ask {name} to draft on {CHANNEL_LABELS[current.channel]}
              </h3>
              <Textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={3}
                        placeholder={`What should it say? ${name} writes from what it knows about you and ${contact.account_name}.`} />
              <div className="flex flex-wrap gap-1.5">
                {NOTE_IDEAS.map((idea) => (
                  <button key={idea} type="button" onClick={() => setNote((prev) => (prev ? `${prev}. ${idea}` : idea))}
                          className="cursor-pointer rounded-full border border-dashed px-2 py-0.5 text-[11px] text-muted-foreground hover:border-theme/50 hover:text-foreground">
                    + {idea}
                  </button>
                ))}
              </div>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground" aria-live="polite">
                  {asked === channel
                    ? waiting ? `${name} is writing it. It appears here, ready to edit.` : "Done. Edit it above, then send."
                    : contact.approved_at ? "Nothing is sent until you send it." : "Asking approves them for outreach. Nothing is sent until you send it."}
                </p>
                <Button size="sm" variant={elsewhere ? "outline" : "default"} onClick={() => void ask()} disabled={asking || waiting}>
                  {asking || waiting ? <Loader2 className="animate-spin" /> : <Sparkles />}
                  {elsewhere ? `Draft on ${CHANNEL_LABELS[current.channel]} anyway` : drafts.length ? "Draft another" : "Draft it"}
                </Button>
              </div>
              {chat.error && <p className="text-xs text-destructive" role="alert">{chat.error}</p>}
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
