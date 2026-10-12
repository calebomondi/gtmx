import { useEffect } from 'react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { markOutreachRead, type OutreachMessageDto } from '@/lib/api'
import { formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import { ChannelGlyph } from './conversation-row'
import { DraftEditor, EDITABLE_STATUSES } from './draft-editor'
import { CHANNELS, initialsFor, type Conversation } from './outreach-types'

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
  const draft = conversation?.dtos.findLast((m) => m.direction === 'outbound' && EDITABLE_STATUSES.has(m.status)) ?? null
  const history = conversation?.dtos.filter((m) => m.id !== draft?.id) ?? []

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
                {draft ? ` · ${draft.thread_id ? 'Reply draft' : 'Draft'} — review before sending` : ''}
              </DialogDescription>
            </div>
            <div className="flex items-center gap-1 rounded-full bg-muted/70 px-2 py-1 text-[10px] font-medium text-muted-foreground">
              <ChannelGlyph icon={channel.icon} className="size-3" />
              {channel.label}
            </div>
          </div>
        </DialogHeader>

        <div className="flex max-h-[65vh] min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          {history.map((message) => <Bubble key={message.id} message={message} />)}
          {draft && (
            <DraftEditor
              workspaceId={workspaceId}
              draft={draft}
              onChanged={onChanged}
              onDeleted={(id) => {
                onDeleted(id)
                if (history.length === 0) onOpenChange(false)
              }}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
