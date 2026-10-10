import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { DotLottieReact } from '@lottiefiles/dotlottie-react'
import {
  AlertTriangle,
  Check,
  Copy,
  Loader2,
  Mail,
  PenLine,
  Sparkles,
  Trash2,
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
import { toast } from 'sonner'
import {
  deleteOutreachMessage,
  draftOutreach,
  listAccounts,
  listOutreach,
  sendOutreachMessage,
  updateOutreachMessage,
  type OutreachMessageDto,
} from '@/lib/api'

import { AgentConnectionsDialog } from './agent-connections-dialog'
import AccountsComponent from './accounts-components'

import {
  CHANNELS,
  formatRelativeTime,
  initialsFor,
  latestMessage,
  matchContactEmail,
  snippetFor,
  toConversation,
  type Channel,
  type ChannelFilter,
  type Conversation,
  type MessageStatus,
  type OutreachFilter,
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

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** Review, edit and approve one outreach message. Email sends through the
 *  user's Gmail on this button only; LinkedIn is copied and sent by hand. */
function ThreadModal({
  workspaceId,
  message,
  open,
  onOpenChange,
  onChanged,
  onDeleted,
}: {
  workspaceId?: string
  message: OutreachMessageDto | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onChanged: (message: OutreachMessageDto) => void
  onDeleted: (messageId: string) => void
}) {
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [address, setAddress] = useState('')
  const [busy, setBusy] = useState<null | 'save' | 'send' | 'delete'>(null)

  useEffect(() => {
    if (!message) return
    setSubject(message.subject ?? '')
    setBody(message.body)
    setAddress(message.recipient_address ?? '')
  }, [message])

  if (!message || !workspaceId) return null
  const channel = CHANNELS[message.channel]
  const editable = message.status === 'draft' || message.status === 'failed'
  const dirty = subject !== (message.subject ?? '') || body !== message.body || address !== (message.recipient_address ?? '')

  const save = async (): Promise<OutreachMessageDto> => {
    const saved = await updateOutreachMessage(workspaceId, message.id, {
      subject: message.channel === 'email' ? subject : undefined,
      body,
      recipient_address: message.channel === 'email' ? address : undefined,
    })
    onChanged(saved)
    return saved
  }

  const act = async (kind: 'save' | 'send' | 'delete') => {
    setBusy(kind)
    try {
      if (kind === 'delete') {
        await deleteOutreachMessage(workspaceId, message.id)
        onDeleted(message.id)
        onOpenChange(false)
        return
      }
      if (dirty) await save()
      if (kind === 'save') {
        toast.success('Draft saved')
        return
      }
      const sent = await sendOutreachMessage(workspaceId, message.id)
      onChanged(sent)
      if (sent.status === 'sent') {
        toast.success(`Sent to ${sent.recipient_address}`)
        onOpenChange(false)
      } else {
        toast.error(sent.error ?? 'The message was not sent.')
      }
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader className="border-b">
          <div className="flex items-center gap-3">
            <Avatar size="lg">
              <AvatarFallback>{initialsFor(message.recipient_name || message.recipient_company)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <DialogTitle className="truncate">{message.recipient_name || message.recipient_company}</DialogTitle>
              <DialogDescription className="truncate">
                {message.recipient_company} · {editable ? 'Draft — review before sending' : `Sent ${message.sent_at ? formatRelativeTime(Date.parse(message.sent_at)) : ''}`}
              </DialogDescription>
            </div>
            <div className="flex items-center gap-1 rounded-full bg-muted/70 px-2 py-1 text-[10px] font-medium text-muted-foreground">
              <ChannelGlyph icon={channel.icon} className="size-3" />
              {channel.label}
            </div>
          </div>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          {message.status === 'failed' && message.error && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" /> {message.error}
            </div>
          )}
          {message.channel === 'email' && (
            <>
              <Input value={address} disabled={!editable} onChange={(e) => setAddress(e.target.value)} placeholder="Recipient email" />
              <Input value={subject} disabled={!editable} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" />
            </>
          )}
          <Textarea value={body} disabled={!editable} onChange={(e) => setBody(e.target.value)} className="min-h-56 resize-y" />
          {message.channel === 'linkedin' && (
            <p className="text-xs text-muted-foreground">LinkedIn doesn't allow apps to send messages: copy this and send it from LinkedIn.</p>
          )}
        </div>

        {editable && (
          <DialogFooter className="border-t">
            <div className="flex w-full items-center justify-between gap-2">
              <Button type="button" size="sm" variant="ghost" className="cursor-pointer text-muted-foreground hover:text-destructive" disabled={busy !== null} onClick={() => void act('delete')}>
                <Trash2 className="size-3.5" /> Delete
              </Button>
              <div className="flex items-center gap-2">
                <Button type="button" size="sm" variant="outline" className="cursor-pointer" disabled={busy !== null || !dirty} onClick={() => void act('save')}>
                  Save
                </Button>
                {message.channel === 'email' ? (
                  <Button type="button" size="sm" className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400 hover:text-amber-950" disabled={busy !== null || !body.trim() || !address.trim() || !subject.trim()} onClick={() => void act('send')}>
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

/** Draft one message per account the user selected for outreach. */
function DraftDialog({
  workspaceId,
  open,
  onOpenChange,
  onStarted,
}: {
  workspaceId?: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onStarted: () => void
}) {
  const [selected, setSelected] = useState<string[] | null>(null)
  const [channel, setChannel] = useState<Channel>('email')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !workspaceId) return
    setSelected(null)
    listAccounts(workspaceId)
      .then((list) => setSelected(list.accounts.filter((a) => a.selected).map((a) => a.id)))
      .catch(() => setSelected([]))
  }, [open, workspaceId])

  const start = async () => {
    if (!workspaceId || !selected?.length) return
    setBusy(true)
    try {
      await draftOutreach(workspaceId, selected.slice(0, 25), channel)
      toast.success('Drafting started — drafts appear here in a minute')
      onStarted()
      onOpenChange(false)
    } catch (err) {
      toast.error(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Draft outreach</DialogTitle>
          <DialogDescription>
            The agent writes one personalized message per selected account. You review every one — nothing is sent without you.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 px-4 pb-2 text-sm">
          {selected === null ? (
            <p className="text-muted-foreground">Loading accounts…</p>
          ) : selected.length === 0 ? (
            <p className="text-muted-foreground">No accounts selected yet. Open Accounts, mark the ones to reach, then come back.</p>
          ) : (
            <p>{selected.length} selected account{selected.length === 1 ? '' : 's'}{selected.length > 25 ? ' (the first 25 will be drafted)' : ''}.</p>
          )}
          <div className="flex gap-2">
            {ENABLED_CHANNELS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setChannel(key)}
                className={cn(
                  'inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium',
                  channel === key ? 'border-amber-500 bg-amber-500 text-amber-950' : 'border-border text-muted-foreground',
                )}
              >
                <ChannelGlyph icon={CHANNELS[key].icon} className="size-3.5" /> {CHANNELS[key].label}
              </button>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button type="button" size="sm" disabled={busy || !selected?.length} onClick={() => void start()} className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400">
            {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />} Draft messages
          </Button>
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
  const [messages, setMessages] = useState<OutreachMessageDto[]>([])
  const [drafting, setDrafting] = useState(false)
  const [draftOpen, setDraftOpen] = useState(false)
  const conversations = useMemo<Conversation[]>(() => messages.map(toConversation), [messages])

  const refresh = useCallback(async () => {
    if (!workspaceId) return
    try {
      const list = await listOutreach(workspaceId)
      setMessages(list.messages)
      setDrafting(list.drafting_run !== null)
    } catch {
      // keep what we have; the next refresh retries
    }
  }, [workspaceId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // While the agent drafts, poll until the drafts land.
  useEffect(() => {
    if (!drafting) return
    const timer = window.setInterval(() => void refresh(), 4000)
    return () => window.clearInterval(timer)
  }, [drafting, refresh])
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

  const activeMessage = messages.find((m) => m.id === threadConversationId) ?? null

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
    setThreadConversationId(id)
    setThreadOpen(true)
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
            className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400"
            disabled={drafting}
            onClick={() => setDraftOpen(true)}
          >
            {drafting ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
            {drafting ? 'Drafting…' : 'Draft outreach'}
          </Button>
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
        workspaceId={workspaceId}
        message={activeMessage}
        open={threadOpen}
        onOpenChange={setThreadOpen}
        onChanged={(updated) => setMessages((prev) => prev.map((m) => (m.id === updated.id ? updated : m)))}
        onDeleted={(id) => setMessages((prev) => prev.filter((m) => m.id !== id))}
      />
      <DraftDialog
        workspaceId={workspaceId}
        open={draftOpen}
        onOpenChange={setDraftOpen}
        onStarted={() => {
          setDrafting(true)
          void refresh()
        }}
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