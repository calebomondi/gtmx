import { useEffect, useState } from 'react'
import { AlertTriangle, Copy, Loader2, Send, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  deleteOutreachMessage,
  sendOutreachMessage,
  updateOutreachMessage,
  type OutreachMessageDto,
} from '@/lib/api'

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export const EDITABLE_STATUSES = new Set<OutreachMessageDto['status']>(['draft', 'failed'])

/** Review, edit and approve one draft. Email sends through the user's Gmail
 *  on this button only; LinkedIn is copied and sent by hand. A draft in a
 *  thread is a reply: it needs no subject. */
export function DraftEditor({
  workspaceId,
  draft,
  onChanged,
  onDeleted,
}: {
  workspaceId: string
  draft: OutreachMessageDto
  onChanged: (message: OutreachMessageDto) => void
  onDeleted: (messageId: string) => void
}) {
  const [subject, setSubject] = useState(draft.subject ?? '')
  const [body, setBody] = useState(draft.body)
  const [address, setAddress] = useState(draft.recipient_address ?? '')
  const [busy, setBusy] = useState<null | 'save' | 'send' | 'delete'>(null)

  useEffect(() => {
    setSubject(draft.subject ?? '')
    setBody(draft.body)
    setAddress(draft.recipient_address ?? '')
  }, [draft])

  const isReply = Boolean(draft.thread_id)
  const email = draft.channel === 'email'
  const dirty = subject !== (draft.subject ?? '') || body !== draft.body || address !== (draft.recipient_address ?? '')
  const canSend = Boolean(body.trim() && address.trim() && (isReply || subject.trim()))

  const save = async () => {
    const saved = await updateOutreachMessage(workspaceId, draft.id, {
      subject: email && !isReply ? subject : undefined,
      body,
      recipient_address: email ? address : undefined,
    })
    onChanged(saved)
  }

  const act = async (kind: 'save' | 'send' | 'delete') => {
    setBusy(kind)
    try {
      if (kind === 'delete') {
        await deleteOutreachMessage(workspaceId, draft.id)
        onDeleted(draft.id)
        return
      }
      if (dirty) await save()
      if (kind === 'save') {
        toast.success('Draft saved')
        return
      }
      const sent = await sendOutreachMessage(workspaceId, draft.id)
      onChanged(sent)
      if (sent.status === 'sent') toast.success(`Sent to ${sent.recipient_address}`)
      else toast.error(sent.error ?? 'The message was not sent.')
    } catch (err) {
      toast.error(errorText(err))
    } finally {
      setBusy(null)
    }
  }

  const copy = async () => {
    try {
      if (dirty) await save()
      await navigator.clipboard.writeText(body)
      toast.success('Copied — paste it into LinkedIn')
    } catch (err) {
      toast.error(errorText(err))
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {draft.status === 'failed' && draft.error && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" /> {draft.error}
        </div>
      )}
      {email && (
        <>
          <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Recipient email" aria-label="Recipient email" />
          {!isReply && <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" aria-label="Subject" />}
        </>
      )}
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} className="min-h-48 resize-y" aria-label="Message" />
      {draft.channel === 'linkedin' && (
        <p className="text-xs text-muted-foreground">LinkedIn doesn't allow apps to send messages: copy this and send it from LinkedIn.</p>
      )}
      <div className="flex w-full items-center justify-between gap-2">
        <Button type="button" size="sm" variant="ghost" className="cursor-pointer text-muted-foreground hover:text-destructive" disabled={busy !== null} onClick={() => void act('delete')}>
          <Trash2 className="size-3.5" /> Delete draft
        </Button>
        <div className="flex items-center gap-2">
          <Button type="button" size="sm" variant="outline" className="cursor-pointer" disabled={busy !== null || !dirty} onClick={() => void act('save')}>
            Save
          </Button>
          {email ? (
            <Button type="button" size="sm" className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950" disabled={busy !== null || !canSend} onClick={() => void act('send')}>
              {busy === 'send' ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />} Approve & send
            </Button>
          ) : (
            <Button type="button" size="sm" className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950" onClick={() => void copy()}>
              <Copy className="size-3.5" /> Copy message
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
