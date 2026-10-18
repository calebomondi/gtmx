import { useState } from "react"
import { Check, Copy, ExternalLink, Loader2, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { LaceOutreachDto, LaceOutreachChanges } from "@/lib/api"

const EDITABLE = new Set(["draft", "failed"])

function DraftCard({ message, onSave, onDiscard }: {
  message: LaceOutreachDto
  onSave: (changes: LaceOutreachChanges) => void
  onDiscard: () => void
}) {
  const [subject, setSubject] = useState(message.subject ?? "")
  const [body, setBody] = useState(message.body)
  const [copied, setCopied] = useState(false)
  const editable = EDITABLE.has(message.status)
  const changed = subject !== (message.subject ?? "") || body !== message.body
  const isLinkedIn = message.channel === "linkedin"

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
        {message.status !== "draft" && <Badge variant="secondary">{message.status}</Badge>}
      </div>
      {!isLinkedIn && (
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!editable}
               aria-label="Subject" placeholder="Subject" />
      )}
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} disabled={!editable}
                aria-label="Message" className="min-h-40 text-sm" />
      {message.error && <p className="text-xs text-destructive">{message.error}</p>}
      {editable && (
        <div className="flex flex-wrap items-center gap-2">
          {changed && (
            <Button size="sm" onClick={() => onSave({ subject: isLinkedIn ? message.subject : subject, body })}>
              Save changes
            </Button>
          )}
          {isLinkedIn && (
            <>
              <Button size="sm" variant="outline" onClick={() => void copy()}>
                {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}
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

/** Messages the Lace drafted. Nothing is sent without the founder. */
export function LaceOutreach({ outreach, drafting, onSave, onDiscard }: {
  outreach: LaceOutreachDto[]
  drafting: boolean
  onSave: (id: string, changes: LaceOutreachChanges) => void
  onDiscard: (id: string) => void
}) {
  const outbound = outreach.filter((m) => m.direction === "outbound")
  return (
    <div className="flex flex-col gap-4">
      {drafting && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Loader2 className="size-4 animate-spin" /> Drafting messages. This takes a few minutes.
        </p>
      )}
      {outbound.length === 0 && !drafting && (
        <p className="text-sm text-muted-foreground">No drafts yet. Ask your Lace to draft outreach to your accounts.</p>
      )}
      <ul className="flex flex-col gap-4">
        {outbound.map((m) => (
          <DraftCard key={m.id} message={m} onSave={(changes) => onSave(m.id, changes)} onDiscard={() => onDiscard(m.id)} />
        ))}
      </ul>
    </div>
  )
}
