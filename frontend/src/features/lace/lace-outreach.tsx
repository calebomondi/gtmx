import { useState } from "react"
import { Check, Copy, ExternalLink, Loader2, Send, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { LaceOutreachDto, LaceOutreachChanges } from "@/lib/api"

const EDITABLE = new Set(["draft", "failed"])

function DraftCard({ message, onSave, onDiscard, onSend, onMarkSent }: {
  message: LaceOutreachDto
  onSave: (changes: LaceOutreachChanges) => void
  onDiscard: () => void
  onSend: () => void
  onMarkSent: () => void
}) {
  const [address, setAddress] = useState(message.recipient_address ?? "")
  const [subject, setSubject] = useState(message.subject ?? "")
  const [body, setBody] = useState(message.body)
  const [copied, setCopied] = useState(false)
  const editable = EDITABLE.has(message.status)
  const changed = subject !== (message.subject ?? "") || body !== message.body
    || address !== (message.recipient_address ?? "")
  const isLinkedIn = message.channel === "linkedin"
  // An answer goes into the existing thread, under its subject.
  const isReply = Boolean(message.thread_id) && message.status === "draft"

  const copy = async () => {
    await navigator.clipboard.writeText(body)
    setCopied(true)
  }

  return (
    <li className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{message.recipient_name ?? message.recipient_address}</span>
        <span className="text-muted-foreground">at {message.recipient_company}</span>
        <Badge variant="outline">{isLinkedIn ? "LinkedIn" : "Email"}</Badge>
        {isReply && <Badge variant="secondary">reply</Badge>}
        {message.status !== "draft" && <Badge variant="secondary">{message.status}</Badge>}
      </div>
      {!isLinkedIn && (
        <>
          <Input value={address} onChange={(e) => setAddress(e.target.value)} disabled={!editable}
                 aria-label="Recipient email" placeholder="name@company.com" inputMode="email" />
          {!isReply && (
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!editable}
                   aria-label="Subject" placeholder="Subject" />
          )}
        </>
      )}
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} disabled={!editable}
                aria-label="Message" className="min-h-40 text-sm" />
      {message.error && <p className="text-xs text-destructive">{message.error}</p>}
      {editable && (
        <div className="flex flex-wrap items-center gap-2">
          {changed && (
            <Button size="sm" variant="outline"
                    onClick={() => onSave(isLinkedIn ? { body } : { subject, body, recipient_address: address })}>
              Save changes
            </Button>
          )}
          {!isLinkedIn && (
            // Unsaved edits would not be what goes out: save first.
            <Button size="sm" onClick={onSend} disabled={changed || !message.recipient_address}
                    title={changed ? "Save your changes first" : undefined}>
              <Send /> Send
            </Button>
          )}
          {isLinkedIn && (
            <>
              <Button size="sm" variant="outline" onClick={() => void copy()}>
                {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}
              </Button>
              <Button size="sm" onClick={onMarkSent} disabled={changed}>
                <Check /> I've sent it
              </Button>
              {message.recipient_address && (
                <a href={message.recipient_address} target="_blank" rel="noreferrer"
                   className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline">
                  Open their profile <ExternalLink className="size-3" />
                </a>
              )}
            </>
          )}
          <Button size="sm" variant="ghost" onClick={onDiscard} aria-label="Discard draft">
            <Trash2 /> Discard
          </Button>
        </div>
      )}
    </li>
  )
}

const INTENT_LABELS: Record<string, string> = {
  interested: "Interested", question: "Asked a question", objection: "Raised an objection",
  meeting_request: "Wants to meet", not_now: "Not now", unsubscribe: "Asked to stop",
  out_of_office: "Out of office", referral: "Referred you on",
}

function ReplyCard({ message }: { message: LaceOutreachDto }) {
  return (
    <li className="flex flex-col gap-1 rounded-lg border bg-muted/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{message.recipient_name ?? message.recipient_address}</span>
        <span className="text-muted-foreground">at {message.recipient_company}</span>
        <Badge variant={message.intent === "unsubscribe" ? "destructive" : "default"}>
          {message.intent ? INTENT_LABELS[message.intent] ?? message.intent : "Reading…"}
        </Badge>
      </div>
      <p className="line-clamp-6 whitespace-pre-wrap text-muted-foreground">{message.body}</p>
    </li>
  )
}

/** Messages the Lace drafted. Nothing is sent without the founder: Send is
 * their approval, and LinkedIn messages they send by hand. */
export function LaceOutreach({ outreach, drafting, onSave, onDiscard, onSend, onMarkSent }: {
  outreach: LaceOutreachDto[]
  drafting: boolean
  onSave: (id: string, changes: LaceOutreachChanges) => void
  onDiscard: (id: string) => void
  onSend: (id: string) => void
  onMarkSent: (id: string) => void
}) {
  const outbound = outreach.filter((m) => m.direction === "outbound")
  const replies = outreach.filter((m) => m.direction === "inbound" && m.status === "received")
  return (
    <div className="flex flex-col gap-4">
      {drafting && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Loader2 className="size-4 animate-spin" /> Drafting messages. This takes a few minutes.
        </p>
      )}
      {replies.length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Replies</h3>
          <ul className="flex flex-col gap-2">{replies.map((m) => <ReplyCard key={m.id} message={m} />)}</ul>
        </section>
      )}
      {outbound.length === 0 && !drafting && (
        <p className="text-sm text-muted-foreground">No drafts yet. Ask your Lace to draft outreach to your accounts.</p>
      )}
      <ul className="flex flex-col gap-4">
        {outbound.map((m) => (
          <DraftCard key={m.id} message={m} onSave={(changes) => onSave(m.id, changes)} onDiscard={() => onDiscard(m.id)}
                     onSend={() => onSend(m.id)} onMarkSent={() => onMarkSent(m.id)} />
        ))}
      </ul>
    </div>
  )
}
