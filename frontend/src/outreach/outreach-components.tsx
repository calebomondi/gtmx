import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { DotLottieReact } from '@lottiefiles/dotlottie-react'
import {
  AlertTriangle,
  Check,
  Mail,
  Paperclip,
  PenLine,
  Link,
  Pin,
  Reply,
  Search,
  Send,
  UsersIcon,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

import { AgentConnectionsDialog } from './agent-connections-dialog'
import AccountsComponent from './accounts-components'

import {
  CHANNELS,
  formatRelativeTime,
  initialsFor,
  latestMessage,
  matchContactEmail,
  snippetFor,
  type Channel,
  type ChannelFilter,
  type Conversation,
  type MessageStatus,
  type OutreachFilter,
  type OutreachMessage,
} from './outreach-types'

const DAY_MS = 24 * 60 * 60 * 1000

const STATUS_META: Record<MessageStatus, { icon: React.ReactNode; label: string }> = {
  sent: { icon: <Check className="size-3" />, label: 'sent' },
  opened: { icon: <Mail className="size-3" />, label: 'opened' },
  replied: { icon: <Reply className="size-3" />, label: 'replied' },
  bounced: { icon: <AlertTriangle className="size-3" />, label: 'bounced' },
  failed: { icon: <X className="size-3" />, label: 'failed' },
  draft: { icon: <PenLine className="size-3" />, label: 'draft' },
}

const FOLDER_CHIPS: { value: OutreachFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'inbox', label: 'Inbox' },
  { value: 'sent', label: 'Sent' },
  { value: 'drafts', label: 'Drafts' },
  { value: 'bounces', label: 'Bounces' },
]

const ENABLED_CHANNELS: Channel[] = ['email', 'linkedin']

function ChannelGlyph({
  icon,
  className,
}: {
  icon: LucideIcon | string
  className?: string
}) {
  if (typeof icon === 'string') {
    return <img src={icon} alt="" aria-hidden className={className} />
  }
  const Icon = icon
  return <Icon className={className} />
}

function splitIntoSections(conversations: Conversation[]) {
  const needsAttention: Conversation[] = []
  const today: Conversation[] = []
  const earlier: Conversation[] = []

  for (const conversation of conversations) {
    if (conversation.unread) {
      needsAttention.push(conversation)
    } else if (now() - conversation.lastActivityAt < DAY_MS) {
      today.push(conversation)
    } else {
      earlier.push(conversation)
    }
  }

  const byTime = (a: Conversation, b: Conversation) => b.lastActivityAt - a.lastActivityAt
  needsAttention.sort(byTime)
  today.sort(byTime)
  earlier.sort(byTime)

  return { needsAttention, today, earlier }
}

const now = () => Date.now()

function ConversationRow({
  conversation,
  selected,
  onSelect,
  onTogglePin,
}: {
  conversation: Conversation
  selected: boolean
  onSelect: () => void
  onTogglePin: () => void
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
        'group flex w-full cursor-pointer items-center gap-3 rounded-lg border p-3 text-left transition-colors shadow-xs',
        selected
          ? 'border-amber-500/40 bg-muted/60'
          : 'border-transparent hover:border-primary/10 hover:bg-muted/40',
        conversation.unread && 'border-amber-500/25',
      )}
    >
      {/* <Avatar
        size="default"
        className={cn(
          'shrink-0',
          conversation.unread ? 'border-2 border-amber-500/40' : '',
        )}
      >
        <AvatarFallback>{initialsFor(conversation.contact.name)}</AvatarFallback>
      </Avatar> */}

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <ChannelGlyph icon={channel.icon} className="size-3 shrink-0 text-muted-foreground" />
          <span
            className={cn(
              'truncate text-sm font-medium',
              conversation.unread ? 'text-foreground' : 'text-muted-foreground',
            )}
          >
            {conversation.contact.name}
          </span>
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {formatRelativeTime(conversation.lastActivityAt)}
          </span>
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-2">
          <span className="truncate text-xs text-muted-foreground">
            {conversation.contact.company !== '—' ? conversation.contact.company : ''}
            {conversation.contact.company !== '—' ? ' · ' : ''}
            {snippetFor(conversation)}
          </span>
          {latest && !conversation.unread && (
            <span className="shrink-0 text-muted-foreground">{STATUS_META[latest.status].icon}</span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-1">
        {conversation.unread && (
          <span className="size-1.5 rounded-full bg-amber-500" />
        )}
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          aria-label="Pin conversation"
          className={cn(
            'opacity-0 transition-opacity group-hover:opacity-100',
            'opacity-100 text-amber-500 hover:text-amber-500',
          )}
          onClick={(event) => {
            event.stopPropagation()
            onTogglePin()
          }}
        >
          <Pin className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}

function SectionHeader({ label, count }: { label: string; count: number }) {
  if (count === 0) return null
  return (
    <div className="flex items-center gap-2 px-1 pt-4 pb-2 first:pt-2">
      <span className="text-[12px] font-semibold tracking-wide text-muted-foreground uppercase">
        {label}
      </span>
      <span className="rounded-full bg-muted/70 px-1.5 py-0.5 text-[11.5px] text-muted-foreground">
        {count}
      </span>
    </div>
  )
}

function MessageBubble({ message }: { message: OutreachMessage }) {
  const outbound = message.direction === 'outbound'
  const status = STATUS_META[message.status]

  return (
    <div className={cn('flex w-full flex-col', outbound ? 'items-end' : 'items-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-xl border px-3 py-2 text-sm leading-relaxed',
          outbound
            ? 'border-amber-500/20 bg-amber-500/10 text-foreground'
            : 'border-primary/10 bg-muted/60 text-foreground',
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.body}</p>
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <span>{formatRelativeTime(message.timestamp)}</span>
        <span className="inline-flex items-center gap-1">
          {status.icon}
          {status.label}
        </span>
      </div>
    </div>
  )
}

function ThreadModal({
  conversation,
  open,
  onOpenChange,
  onSendReply,
}: {
  conversation: Conversation | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSendReply: (conversationId: string, body: string) => void
}) {
  const [replyText, setReplyText] = useState('')
  const channel = conversation ? CHANNELS[conversation.channel] : null

  useEffect(() => {
    if (!open) {
      setReplyText('')
    }
  }, [open, conversation?.id])

  if (!conversation || !channel) return null

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
                {conversation.contact.email ? ` · ${conversation.contact.email}` : ''}
              </DialogDescription>
            </div>
            <div className="flex items-center gap-1 rounded-full bg-muted/70 px-2 py-1 text-[10px] font-medium text-muted-foreground">
              <ChannelGlyph icon={channel.icon} className="size-3" />
              {channel.label}
            </div>
          </div>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          {conversation.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </div>

        <DialogFooter className="border-t">
          <div className="flex w-full flex-col gap-2">
            <div className="flex items-center gap-2">
              <Textarea
                value={replyText}
                onChange={(event) => setReplyText(event.target.value)}
                placeholder="Write a reply…"
                className="min-h-20 resize-none"
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                className="cursor-pointer text-muted-foreground"
              >
                <Paperclip className="size-4" />
              </Button>
              <Button
                type="button"
                size="sm"
                className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950"
                disabled={!replyText.trim()}
                onClick={() => {
                  onSendReply(conversation.id, replyText.trim())
                  setReplyText('')
                }}
              >
                <Send className="size-3.5" />
                Send
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export interface OutReachComponentProps {
  focusEmail?: string | null
  onFocusHandled?: () => void
  workspaceId?: string
}

export function OutReachComponent({ focusEmail = null, onFocusHandled, workspaceId }: OutReachComponentProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [filter, setFilter] = useState<OutreachFilter>('all')
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>('all')
  const [query, setQuery] = useState('')
  const [threadConversationId, setThreadConversationId] = useState<string | null>(null)
  const [threadOpen, setThreadOpen] = useState(false)
  const [connectOpen, setConnectOpen] = useState(false)
  const [showAccounts, setShowAccounts] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const accountsBoxRef = useRef<HTMLDivElement>(null)
  const [accountsFill, setAccountsFill] = useState<number | null>(null)

  // Measure the vertical space left below the header so the accounts card
  // occupies the whole available height (and its list scrolls inside).
  useLayoutEffect(() => {
    if (!showAccounts) return
    const update = () => {
      const root = rootRef.current
      const box = accountsBoxRef.current
      if (!root || !box) return
      const available = Math.max(
        160,
        // 12px kept back for the gap below the card (formerly the box's mb-3).
        Math.round(root.getBoundingClientRect().bottom - box.getBoundingClientRect().top - 12),
      )
      setAccountsFill(available)
    }
    update()
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('resize', update)
      // Force a fresh measurement the next time the card is opened.
      setAccountsFill(null)
    }
  }, [showAccounts])

  const filtered = useMemo(() => {
    let list = conversations
    if (filter !== 'all') list = list.filter((c) => c.folder === filter)
    if (channelFilter !== 'all') list = list.filter((c) => c.channel === channelFilter)
    if (query.trim()) {
      const q = query.trim().toLowerCase()
      list = list.filter(
        (c) =>
          c.contact.name.toLowerCase().includes(q) ||
          c.contact.company.toLowerCase().includes(q) ||
          snippetFor(c).toLowerCase().includes(q),
      )
    }
    return list
  }, [conversations, filter, channelFilter, query])

  const sections = useMemo(() => splitIntoSections(filtered), [filtered])

  const unreadCount = useMemo(
    () => conversations.filter((c) => c.unread).length,
    [conversations],
  )

  const activeThread = conversations.find((c) => c.id === threadConversationId) ?? null

  useEffect(() => {
    if (focusEmail) {
      const match = matchContactEmail(conversations, focusEmail)
      if (match) {
        setThreadConversationId(match.id)
        setThreadOpen(true)
      }
      onFocusHandled?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusEmail])

  const openThread = (id: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, unread: false } : c)),
    )
    setThreadConversationId(id)
    setThreadOpen(true)
  }

  const sendReply = (id: string, body: string) => {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== id) return c
        const message: OutreachMessage = {
          id: `msg-${Date.now()}`,
          conversationId: id,
          channel: c.channel,
          direction: 'outbound',
          body,
          timestamp: Date.now(),
          status: 'sent',
        }
        return { ...c, messages: [...c.messages, message], lastActivityAt: Date.now() }
      }),
    )
  }

  return (
    <div ref={rootRef} className="flex h-[calc(100dvh-7rem)] min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-medium text-foreground">Reach Out</h2>
          {unreadCount > 0 && (
            <span className="flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-amber-500 px-1 text-xs font-medium text-amber-950">
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="cursor-pointer"
            onClick={() => setShowAccounts((v) => !v)}
          >
            <UsersIcon className="size-3.5" />
            Accounts
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="cursor-pointer"
            onClick={() => setConnectOpen(true)}
          >
            <Link className="size-3.5" />
            Connect
          </Button>
        </div>
      </div>

      <AnimatePresence mode="wait" initial={false}>
        {showAccounts && (
          <motion.div
            key="accounts"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: accountsFill ?? 0, opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div ref={accountsBoxRef} className="relative flex h-full min-h-0 flex-col">
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label="Close accounts"
                className="absolute right-3 top-3 z-10 cursor-pointer text-muted-foreground hover:text-foreground"
                onClick={() => setShowAccounts(false)}
              >
                <X className="size-4" />
              </Button>
              <AccountsComponent workspaceId={workspaceId} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!showAccounts && (
        <>
          <div className="mt-3 flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          {FOLDER_CHIPS.map((chip) => (
            <button
              key={chip.value}
              type="button"
              onClick={() => setFilter(chip.value)}
              className={cn(
                'cursor-pointer rounded-full border px-2.5 py-1.5 text-xs font-medium transition-colors',
                filter === chip.value
                  ? 'border-amber-500 bg-amber-500 text-amber-950'
                  : 'border-border bg-secondary text-secondary-foreground hover:bg-accent hover:text-accent-foreground',
              )}
            >
              {chip.label}
            </button>
          ))}
          <div className="my-1 h-4 w-px bg-border" />
          {ENABLED_CHANNELS.map((channel) => {
            const meta = CHANNELS[channel]
            return (
              <button
                key={channel}
                type="button"
                onClick={() =>
                  setChannelFilter((prev) => (prev === channel ? 'all' : channel))
                }
                className={cn(
                  'inline-flex cursor-pointer items-center gap-1 rounded-full px-2 py-1 text-xs font-medium transition-colors',
                  channelFilter === channel
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                )}
              >
                <ChannelGlyph icon={meta.icon} className="size-3.5" />
                {meta.label}
              </button>
            )
          })}
        </div>
        <hr className="mb-3"/>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search contacts or messages…"
            className="h-8 bg-[#F3F3F3] dark:bg-[#212121] pl-8 text-xs"
          />
        </div>
      </div>

      <div className="mt-3 min-h-0 flex-1 overflow-y-auto pb-2">
        {filtered.length === 0 ? (
          <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 text-center px-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
              <DotLottieReact
                src="/empty.lottie"
                loop
                autoplay
                onError={() => {}}
                className="w-full h-auto"
              />
            </div>
            <p className="text-sm text-muted-foreground">
              {query.trim()
                ? 'No conversations match your search.'
                : 'No conversations here yet. Connect a channel to start reaching out.'}
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            <SectionHeader label="Needs attention" count={sections.needsAttention.length} />
            {sections.needsAttention.map((conversation) => (
              <ConversationRow
                key={conversation.id}
                conversation={conversation}
                selected={conversation.id === threadConversationId}
                onSelect={() => openThread(conversation.id)}
                onTogglePin={() => undefined}
              />
            ))}
            <SectionHeader label="Today" count={sections.today.length} />
            {sections.today.map((conversation) => (
              <ConversationRow
                key={conversation.id}
                conversation={conversation}
                selected={conversation.id === threadConversationId}
                onSelect={() => openThread(conversation.id)}
                onTogglePin={() => undefined}
              />
            ))}
            <SectionHeader label="Earlier" count={sections.earlier.length} />
            {sections.earlier.map((conversation) => (
              <ConversationRow
                key={conversation.id}
                conversation={conversation}
                selected={conversation.id === threadConversationId}
                onSelect={() => openThread(conversation.id)}
                onTogglePin={() => undefined}
              />
            ))}
          </div>
        )}
      </div>

      <ThreadModal
        conversation={activeThread}
        open={threadOpen}
        onOpenChange={setThreadOpen}
        onSendReply={sendReply}
      />
      <AgentConnectionsDialog
        open={connectOpen}
        onOpenChange={setConnectOpen}
      />
        </>
      )}
    </div>
  )
}

export default OutReachComponent