import { useState } from "react"
import { Check, Copy, ExternalLink, Loader2, Mail, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import type { ContactDto, LaceOutreachDto } from "@/lib/api"
import { cn } from "@/lib/utils"

import { DraftCard } from "./lace-draft"
import { Bubble } from "./lace-threads"
import { initials } from "./outreach-threads"
import type { LaceChat } from "./use-lace-chat"

type Channel = "email" | "linkedin"

const NOTE_IDEAS = ["Mention our pilot results", "Keep it under 80 words", "Ask for a 15-minute call"]

/** Everything sent to, drafted for or received from one person. */
function withPerson(outreach: LaceOutreachDto[], contact: ContactDto): LaceOutreachDto[] {
  const addresses = [contact.email, contact.linkedin].filter(Boolean).map((a) => (a as string).toLowerCase())
  return outreach
    .filter((m) => (m.recipient_address && addresses.includes(m.recipient_address.toLowerCase()))
      || (contact.name && m.recipient_name === contact.name && m.recipient_company === contact.account_name))
    .sort((a, b) => (a.sent_at ?? a.created_at).localeCompare(b.sent_at ?? b.created_at))
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

/** One person found at a saved account: how to reach them, every message
 * with them (drafts editable and sendable in place), and a box to ask the
 * Lace to write to them on email or LinkedIn, with what to say. */
export function LaceContactDialog({ contact, channel: initialChannel, name, chat, onClose }: {
  contact: ContactDto
  channel: Channel | null
  name: string
  chat: LaceChat
  onClose: () => void
}) {
  const reachable: Channel[] = [contact.email ? "email" : null, contact.linkedin ? "linkedin" : null]
    .filter((c): c is Channel => c !== null)
  const [channel, setChannel] = useState<Channel | null>(initialChannel ?? reachable[0] ?? null)
  const [note, setNote] = useState("")
  const [asked, setAsked] = useState(false)
  const [asking, setAsking] = useState(false)
  const messages = withPerson(chat.outreach, contact)
  const drafts = messages.filter((m) => m.direction === "outbound" && (m.status === "draft" || m.status === "failed"))
  const said = messages.filter((m) => !drafts.includes(m))
  const who = contact.name ?? contact.email ?? "this person"

  const ask = async () => {
    if (!channel) return
    setAsking(true)
    if (await chat.draftToContact(contact.id, channel, note)) setAsked(true)
    setAsking(false)
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[88svh] overflow-y-auto sm:max-w-xl">
        <DialogHeader className="flex-row items-center gap-3 space-y-0">
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

        <div className="flex flex-col gap-4 px-4 pb-4">
        <div className="flex flex-col gap-1.5 rounded-xl border p-2 text-sm">
          {contact.email && (
            <div className="flex items-center gap-2 px-1">
              <Mail className="size-4 text-muted-foreground" /> <span className="min-w-0 flex-1 truncate">{contact.email}</span>
              <CopyAddress value={contact.email} label="email address" />
            </div>
          )}
          {contact.linkedin && (
            <div className="flex items-center gap-2 px-1">
              <span className="w-4 text-center text-xs font-bold text-muted-foreground">in</span>
              <a href={contact.linkedin} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate hover:underline">
                {contact.linkedin.replace(/^https?:\/\/(www\.)?/, "")}
              </a>
              <ExternalLink className="size-3.5 text-muted-foreground" />
            </div>
          )}
          {reachable.length === 0 && <p className="px-1 text-muted-foreground">No email or LinkedIn on file for them.</p>}
        </div>

        {(said.length > 0 || drafts.length > 0) && (
          <section className="flex flex-col gap-3">
            <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Your conversation</h3>
            {said.map((m) => <Bubble key={m.id} message={m} />)}
            {drafts.map((m) => (
              <DraftCard key={m.id} message={m} sendingSoon={chat.sendingSoon.has(m.id)}
                         onSave={(changes) => void chat.saveDraft(m.id, changes)} onDiscard={() => void chat.discardDraft(m.id)}
                         onSend={() => chat.sendDraft(m.id)} onUndo={() => chat.undoSend(m.id)}
                         onMarkSent={() => void chat.markSent(m.id)} />
            ))}
          </section>
        )}

        {reachable.length > 0 && (
          <section className="flex flex-col gap-3 rounded-xl border border-theme/30 bg-gradient-to-br from-theme/10 via-card to-card p-3">
            <h3 className="flex items-center gap-2 text-sm font-medium"><Sparkles className="size-4 text-theme" /> Ask {name} to draft</h3>
            <div className="flex gap-1.5" role="radiogroup" aria-label="Channel">
              {reachable.map((c) => (
                <button key={c} type="button" role="radio" aria-checked={channel === c} onClick={() => setChannel(c)}
                        className={cn("cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors",
                                      channel === c ? "border-theme/60 bg-theme/15 text-foreground" : "text-muted-foreground hover:text-foreground")}>
                  {c === "email" ? "Email" : "LinkedIn message"}
                </button>
              ))}
            </div>
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
                {asked
                  ? chat.drafting ? `${name} is writing it. It appears here, ready to edit.` : `Done. Edit it above, then send.`
                  : contact.approved_at ? "Nothing is sent until you send it." : "Asking approves them for outreach. Nothing is sent until you send it."}
              </p>
              <Button size="sm" onClick={() => void ask()} disabled={!channel || asking || (asked && chat.drafting)}>
                {asking || (asked && chat.drafting) ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {drafts.length ? "Draft another" : "Draft it"}
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
