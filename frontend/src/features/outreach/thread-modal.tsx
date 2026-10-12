import { useEffect, useState } from 'react'
import { AlertTriangle, Copy, Loader2, Send, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  deleteOutreachMessage,
  markOutreachRead,
  sendOutreachMessage,
  updateOutreachMessage,
  type OutreachMessageDto,
} from '@/lib/api'
import { formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import { ChannelGlyph } from './conversation-row'
import { CHANNELS, initialsFor, type Conversation } from './outreach-types'

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

const EDITABLE = new Set<OutreachMessageDto['status']>(['draft', 'failed'])

function Bubble({ message }: { message: OutreachMessageDto }) {
  const inbound = message.direction === 'inbound'
  const when = message.sent_at ? formatRelativeTime(Date.parse(message.sent_at)) : ''
  return (
    <div className={cn('flex flex-col gap-1', inbound ? 'items-start' : 'items-end')}>
      <div
        className={cn(
          'max-w-[85%] whitespace-pre-wrap rounded-lg border px-3 py-2 text-sm',
          inbound ? 'border-border bg-muted/60' : 'border-amber-500/30 bg-amber-500/5',
          message.status === 'bounced' && 'border-destructive/40 bg-destructive/5',
        )}
      >
        {message.subject && !inbound && <p className="mb-1 text-xs font-medium text-muted-foreground">{message.subject}</p>}
        {message.body}
      </div>
      <span className="text-[11px] text-muted-foreground">
        {inbound ? (message.status === 'bounced' ? 'Bounce notice' : message.recipient_name || message.recipient_address) : 'You'}
        {when && ` · ${when}`}
      </span>
    </div>
  )
}

/** One conversation: what was sent, the replies that came back, and the
 *  draft (if any) to review. Email sends through the user's Gmail on this
 *  button only; LinkedIn is copied and sent by hand. */
export function ThreadModal({
  workspaceId,
  conversation,
  open,
  onOpenChange,
  onChanged,
  onDeleted,
}: {
  workspaceId?: string
  conversation: Conversation | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onChanged: (message: OutreachMessageDto) => void
  onDeleted: (messageId: string) => void
}) {
  const draft = conversation?.dtos.findLast((m) => m.direction === 'outbound' && EDITABLE.has(m.status)) ?? null
  const history = conversation?.dtos.filter((m) => m.id !== draft?.id) ?? []
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [address, setAddress] = useState('')
  const [busy, setBusy] = useState<null | 'save' | 'send' | 'delete'>(null)

  useEffect(() => {
    if (!draft) return
    setSubject(draft.subject ?? '')
    setBody(draft.body)
    setAddress(draft.recipient_address ?? '')
  }, [draft])

  // Opening a conversation reads its replies.
  useEffect(() => {
    if (!open || !workspaceId || !conversation) return
    for (const message of conversation.dtos) {
      if (message.direction === 'inbound' && message.read_at === null) {
        markOutreachRead(workspaceId, message.id).then(onChanged).catch(() => undefined)
      }
    }
  }, [open, workspaceId, conversation, onChanged])

  if (!conversation || !workspaceId) return null
  const channel = CHANNELS[conversation.channel]
  const isReply = Boolean(draft?.thread_id)
  const dirty = draft !== null && (subject !== (draft.subject ?? '') || body !== draft.body || address !== (draft.recipient_address ?? ''))

  const save = async (message: OutreachMessageDto): Promise<OutreachMessageDto> => {
    const saved = await updateOutreachMessage(workspaceId, message.id, {
      subject: message.channel === 'email' && !isReply ? subject : undefined,
      body,
      recipient_address: message.channel === 'email' ? address : undefined,
    })
    onChanged(saved)
    return saved
  }

  const act = async (kind: 'save' | 'send' | 'delete') => {
    if (!draft) return
    setBusy(kind)
    try {
      if (kind === 'delete') {
        await deleteOutreachMessage(workspaceId, draft.id)
        onDeleted(draft.id)
        if (history.length === 0) onOpenChange(false)
        return
      }
      if (dirty) await save(draft)
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
    if (!draft) return
    try {
      if (dirty) await save(draft)
      await navigator.clipboard.writeText(body)
      toast.success('Copied — paste it into LinkedIn')
    } catch (err) {
      toast.error(errorText(err))
    }
  }

  const canSend = body.trim() && address.trim() && (isReply || subject.trim())

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader className="border-b">
          <div className="flex items-center gap-3">
            <Avatar size="lg">
              <AvatarFallback>{initialsFor(conversation.contact.name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <DialogTitle className="truncate">{conversation.contact.name}</DialogTitle>
              <DialogDescription className="truncate">
                {conversation.contact.company}
                {draft ? ` · ${isReply ? 'Reply draft' : 'Draft'} — review before sending` : ''}
              </DialogDescription>
            </div>
            <div className="flex items-center gap-1 rounded-full bg-muted/70 px-2 py-1 text-[10px] font-medium text-muted-foreground">
              <ChannelGlyph icon={channel.icon} className="size-3" />
              {channel.label}
            </div>
          </div>
        </DialogHeader>

        <div className="flex max-h-[60vh] min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          {history.map((message) => <Bubble key={message.id} message={message} />)}
          {draft && (
            <div className="flex flex-col gap-3">
              {draft.status === 'failed' && draft.error && (
                <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" /> {draft.error}
                </div>
              )}
              {draft.channel === 'email' && (
                <>
                  <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Recipient email" />
                  {!isReply && <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" />}
                </>
              )}
              <Textarea value={body} onChange={(e) => setBody(e.target.value)} className="min-h-48 resize-y" />
              {draft.channel === 'linkedin' && (
                <p className="text-xs text-muted-foreground">LinkedIn doesn't allow apps to send messages: copy this and send it from LinkedIn.</p>
              )}
            </div>
          )}
        </div>

        {draft && (
          <DialogFooter className="border-t">
            <div className="flex w-full items-center justify-between gap-2">
              <Button type="button" size="sm" variant="ghost" className="cursor-pointer text-muted-foreground hover:text-destructive" disabled={busy !== null} onClick={() => void act('delete')}>
                <Trash2 className="size-3.5" /> Delete draft
              </Button>
              <div className="flex items-center gap-2">
                <Button type="button" size="sm" variant="outline" className="cursor-pointer" disabled={busy !== null || !dirty} onClick={() => void act('save')}>
                  Save
                </Button>
                {draft.channel === 'email' ? (
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
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}
