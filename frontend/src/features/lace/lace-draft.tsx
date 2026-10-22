import { useState, type ReactNode } from "react"
import { Check, Copy, ExternalLink, Send, Trash2, Undo2 } from "lucide-react"
import { motion } from "motion/react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { LaceOutreachDto, LaceOutreachChanges, OutreachChannel } from "@/lib/api"

import { CHANNEL_LABELS } from "./outreach-threads"
import { UNDO_SEND_MS } from "./use-lace-chat"

const EDITABLE = new Set(["draft", "failed"])
// Sent from here through the founder's own account. X needs it connected;
// without that it is handed over like the rest.
const SENT_FROM_HERE = new Set<OutreachChannel>(["email", "x"])
const ANSWERABLE_IN_THREAD = new Set<OutreachChannel>(["instagram", "facebook"])

/** A message the Lace drafted, editable until it goes. Send is the founder's
 * approval (email, X once connected, and Instagram or Facebook answers);
 * on the other channels, whose APIs cannot start a conversation, they copy
 * it, send it there and mark it sent. A send counts down `UNDO_SEND_MS`,
 * with Undo, before it goes. `brainstorm` sits before Send: the Lace, to
 * work on the draft with. */
export function DraftCard({ message, sendingSoon, onSave, onDiscard, onSend, onUndo, onMarkSent, brainstorm }: {
  message: LaceOutreachDto
  sendingSoon: boolean
  brainstorm?: ReactNode
  onSave: (changes: LaceOutreachChanges) => void
  onDiscard: () => void
  onSend: () => void
  onUndo: () => void
  onMarkSent: () => void
}) {
  const [address, setAddress] = useState(message.recipient_address ?? "")
  const [subject, setSubject] = useState(message.subject ?? "")
  const [body, setBody] = useState(message.body)
  const [copied, setCopied] = useState(false)
  // The text last taken from the server: when the Lace rewrites the draft,
  // the new text replaces what is shown, unless the founder is mid-edit.
  const [seen, setSeen] = useState({ subject: message.subject ?? "", body: message.body })
  if (seen.subject !== (message.subject ?? "") || seen.body !== message.body) {
    if (subject === seen.subject && body === seen.body) {
      setSubject(message.subject ?? "")
      setBody(message.body)
    }
    setSeen({ subject: message.subject ?? "", body: message.body })
  }
  const editable = EDITABLE.has(message.status)
  const changed = subject !== (message.subject ?? "") || body !== message.body
    || address !== (message.recipient_address ?? "")
  const isEmail = message.channel === "email"
  // Instagram and Facebook can answer inside a conversation someone started
  // with the founder's linked account (the server checks the link).
  const sendable = SENT_FROM_HERE.has(message.channel)
    || (ANSWERABLE_IN_THREAD.has(message.channel) && Boolean(message.thread_id))
  // Copy, open the profile, mark sent: every channel but email.
  const handoff = !isEmail
  // An answer goes into the existing thread, under its subject.
  const isReply = Boolean(message.thread_id) && message.status === "draft"

  const copy = async () => {
    await navigator.clipboard.writeText(body)
    setCopied(true)
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-dashed border-theme/50 p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">{message.status === "failed" ? "Not sent" : isReply ? "Draft answer" : "Draft"}</Badge>
        {!isReply && <span>to {message.recipient_name ?? message.recipient_address} by {CHANNEL_LABELS[message.channel]}</span>}
      </div>
      {isEmail && (
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
      {editable && sendingSoon && (
        <div className="flex items-center gap-3" aria-live="polite">
          <span className="text-sm">Sending…</span>
          <span aria-hidden className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
            <motion.span className="block h-full origin-left bg-theme" initial={{ scaleX: 1 }} animate={{ scaleX: 0 }}
                         transition={{ duration: UNDO_SEND_MS / 1000, ease: "linear" }} />
          </span>
          <Button size="sm" variant="outline" onClick={onUndo}><Undo2 /> Undo</Button>
        </div>
      )}
      {editable && !sendingSoon && (
        <div className="flex flex-wrap items-center gap-2">
          {brainstorm}
          {changed && (
            <Button size="sm" variant="outline"
                    onClick={() => onSave(isEmail ? { subject, body, recipient_address: address } : { body })}>
              Save changes
            </Button>
          )}
          {sendable && (
            // Unsaved edits would not be what goes out: save first.
            <Button size="sm" onClick={onSend} disabled={changed || !message.recipient_address}
                    title={changed ? "Save your changes first" : undefined}>
              <Send /> Send
            </Button>
          )}
          {handoff && (
            <>
              <Button size="sm" variant="outline" onClick={() => void copy()}>
                {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}
              </Button>
              <Button size="sm" onClick={onMarkSent} disabled={changed}>
                <Check /> I've sent it
              </Button>
              {message.recipient_address?.startsWith("http") && (
                <a href={message.recipient_address} target="_blank" rel="noreferrer"
                   className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline">
                  Open on {CHANNEL_LABELS[message.channel]} <ExternalLink className="size-3" />
                </a>
              )}
            </>
          )}
          <Button size="sm" variant="ghost" onClick={onDiscard} aria-label="Discard draft">
            <Trash2 /> Discard
          </Button>
        </div>
      )}
    </div>
  )
}
