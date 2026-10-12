import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { DotLottieReact } from '@lottiefiles/dotlottie-react'
import { Link, Loader2, RefreshCw, Search, UsersIcon, X } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { listOutreach, syncOutreach, type OutreachMessageDto } from '@/lib/api'
import { cn } from '@/lib/utils'

import AccountsComponent from './accounts-components'
import { AgentConnectionsDialog } from './agent-connections-dialog'
import { ChannelGlyph, ConversationRow } from './conversation-row'
import {
  CHANNEL_ORDER,
  CHANNELS,
  FOLDERS,
  inFolder,
  matchContactEmail,
  snippetFor,
  toConversations,
  type Channel,
  type ChannelFilter,
  type Conversation,
  type OutreachFilter,
} from './outreach-types'
import { ThreadModal } from './thread-modal'
import { useConnectedChannels } from './use-outreach-channels'

const DAY_MS = 24 * 60 * 60 * 1000

function splitIntoSections(conversations: Conversation[]) {
  const now = Date.now()
  const byTime = (a: Conversation, b: Conversation) => b.lastActivityAt - a.lastActivityAt
  const sorted = [...conversations].sort(byTime)
  return {
    needsAttention: sorted.filter((c) => c.unread || c.needsReply),
    today: sorted.filter((c) => !c.unread && !c.needsReply && now - c.lastActivityAt < DAY_MS),
    earlier: sorted.filter((c) => !c.unread && !c.needsReply && now - c.lastActivityAt >= DAY_MS),
  }
}

function SectionHeader({ label, count }: { label: string; count: number }) {
  if (count === 0) return null
  return (
    <div className="flex items-center gap-2 px-1 pt-4 pb-2 first:pt-2">
      <span className="text-[12px] font-semibold tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className="rounded-full bg-muted/70 px-1.5 py-0.5 text-[11.5px] text-muted-foreground">{count}</span>
    </div>
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
  const conversations = useMemo(() => toConversations(messages), [messages])
  const connected = useConnectedChannels()
  // Channels to offer: every live account, plus any channel that already has
  // conversations (LinkedIn drafts need no connection).
  const channels = useMemo<Channel[]>(() => {
    const present = new Set<Channel>([...(connected ?? []), ...conversations.map((c) => c.channel)])
    return CHANNEL_ORDER.filter((channel) => present.has(channel))
  }, [connected, conversations])
  const [syncing, setSyncing] = useState(false)

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

  const checkReplies = useCallback(async (announce: boolean) => {
    if (!workspaceId) return
    setSyncing(true)
    try {
      const { replies, bounced } = await syncOutreach(workspaceId)
      if (replies || bounced) await refresh()
      if (announce) {
        toast.success(replies || bounced
          ? `${replies} new repl${replies === 1 ? 'y' : 'ies'}${bounced ? `, ${bounced} bounced` : ''}`
          : 'No new replies')
      }
    } catch (err) {
      if (announce) toast.error(err instanceof Error ? err.message : String(err))
    } finally {
      setSyncing(false)
    }
  }, [workspaceId, refresh])

  // Replies also sync on a schedule; opening the tab checks right away.
  useEffect(() => {
    void checkReplies(false)
  }, [checkReplies])

  // While the agent drafts, poll until the drafts land.
  useEffect(() => {
    if (!drafting) return
    const timer = window.setInterval(() => void refresh(), 4000)
    return () => window.clearInterval(timer)
  }, [drafting, refresh])
  const [filter, setFilter] = useState<OutreachFilter>('all')
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>('all')
  const selectChannel = (channel: ChannelFilter) => {
    setChannelFilter(channel)
    setFilter(FOLDERS[channel][0].value)
  }
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
    let list = conversations.filter((c) => inFolder(c, channelFilter, filter))
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

  const activeConversation = conversations.find((c) => c.id === threadConversationId) ?? null
  const onMessageChanged = useCallback(
    (updated: OutreachMessageDto) => setMessages((prev) => prev.map((m) => (m.id === updated.id ? updated : m))),
    [],
  )

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
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="whitespace-nowrap text-xl font-medium text-foreground">Reach Out</h2>
          {unreadCount > 0 && (
            <span className="flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-amber-500 px-1 text-xs font-medium text-amber-950">
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {drafting && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> Drafting…
            </span>
          )}
          <Button
            type="button"
            size="icon-sm"
            variant="outline"
            className="cursor-pointer"
            aria-label="Check for replies"
            title="Check for replies"
            disabled={syncing}
            onClick={() => void checkReplies(true)}
          >
            <RefreshCw className={cn('size-3.5', syncing && 'animate-spin')} />
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
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          {(['all', ...channels] as ChannelFilter[]).map((channel) => (
            <button
              key={channel}
              type="button"
              aria-pressed={channelFilter === channel}
              onClick={() => selectChannel(channel)}
              className={cn(
                'inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-xs font-medium transition-colors',
                channelFilter === channel
                  ? 'border-foreground/20 bg-muted text-foreground'
                  : 'border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground',
              )}
            >
              {channel !== 'all' && <ChannelGlyph icon={CHANNELS[channel].icon} className="size-3.5" />}
              {channel === 'all' ? 'All accounts' : CHANNELS[channel].label}
            </button>
          ))}
          {connected !== null && channels.length === 0 && (
            <span className="text-xs text-muted-foreground">No accounts connected yet.</span>
          )}
        </div>
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          {FOLDERS[channelFilter].map((chip) => (
            <button
              key={chip.value}
              type="button"
              aria-pressed={filter === chip.value}
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
              />
            ))}
            <SectionHeader label="Today" count={sections.today.length} />
            {sections.today.map((conversation) => (
              <ConversationRow
                key={conversation.id}
                conversation={conversation}
                selected={conversation.id === threadConversationId}
                onSelect={() => openThread(conversation.id)}
              />
            ))}
            <SectionHeader label="Earlier" count={sections.earlier.length} />
            {sections.earlier.map((conversation) => (
              <ConversationRow
                key={conversation.id}
                conversation={conversation}
                selected={conversation.id === threadConversationId}
                onSelect={() => openThread(conversation.id)}
              />
            ))}
          </div>
        )}
      </div>

      <ThreadModal
        workspaceId={workspaceId}
        conversation={activeConversation}
        open={threadOpen}
        onOpenChange={setThreadOpen}
        onChanged={onMessageChanged}
        onDeleted={(id) => setMessages((prev) => prev.filter((m) => m.id !== id))}
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