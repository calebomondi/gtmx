import type { ReactNode } from 'react'
import { AlertTriangle, Check, PenLine, Reply, X } from 'lucide-react'

import { formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import {
  CHANNELS,
  latestMessage,
  snippetFor,
  type ChannelGlyph as Glyph,
  type Conversation,
  type MessageStatus,
} from './outreach-types'

const STATUS_ICON: Record<MessageStatus, ReactNode> = {
  sent: <Check className="size-3" />,
  replied: <Reply className="size-3" />,
  bounced: <AlertTriangle className="size-3" />,
  failed: <X className="size-3" />,
  draft: <PenLine className="size-3" />,
}

export function ChannelGlyph({ icon, className }: { icon: Glyph; className?: string }) {
  if (typeof icon === 'string') return <img src={icon} alt="" aria-hidden className={className} />
  const Icon = icon
  return <Icon className={className} />
}

export function ConversationRow({
  conversation,
  selected,
  onSelect,
}: {
  conversation: Conversation
  selected: boolean
  onSelect: () => void
}) {
  const channel = CHANNELS[conversation.channel]
  const latest = latestMessage(conversation)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect()
        }
      }}
      className={cn(
        'group flex w-full cursor-pointer items-center gap-3 rounded-lg border p-3 text-left shadow-xs transition-colors',
        selected ? 'border-amber-500/40 bg-muted/60' : 'border-transparent hover:border-primary/10 hover:bg-muted/40',
        conversation.unread && 'border-amber-500/25',
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <ChannelGlyph icon={channel.icon} className="size-3 shrink-0 text-muted-foreground" />
          <span className={cn('truncate text-sm font-medium', conversation.unread ? 'text-foreground' : 'text-muted-foreground')}>
            {conversation.contact.name}
          </span>
          {conversation.messages.length > 1 && (
            <span className="shrink-0 text-xs text-muted-foreground">{conversation.messages.length}</span>
          )}
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {formatRelativeTime(conversation.lastActivityAt)}
          </span>
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-2">
          <span className="truncate text-xs text-muted-foreground">
            {conversation.contact.company && conversation.contact.company !== conversation.contact.name
              ? `${conversation.contact.company} · `
              : ''}
            {snippetFor(conversation)}
          </span>
          {latest && !conversation.unread && (
            <span className="shrink-0 text-muted-foreground" aria-label={latest.status}>{STATUS_ICON[latest.status]}</span>
          )}
        </div>
      </div>
      {conversation.unread && <span className="size-1.5 shrink-0 rounded-full bg-amber-500" aria-label="Unread" />}
    </div>
  )
}
