import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Bot, Loader2 } from 'lucide-react'

import { PromptInputWithActions } from '@/components/chat-input'
import { AvatarImg, SpecialistAvatarGroup, type Specialist } from '@/components/specialist-avatargroup'
import { Markdown } from '@/components/ui/markdown'
import { getChat, sendChat, workspaceDisplayName, type ChatThread } from '@/lib/api'
import { useWorkspaces } from '@/lib/workspaces-store'
import { useWorkspaceSpecialists } from '@/lib/specialists'
import { cn } from '@/lib/utils'

const POLL_MS = 2000

/** The team member who answered, matching "product" to a service expert too. */
function speakerFor(specialists: Specialist[], domain: string | null): { specialist: Specialist; index: number } | null {
  if (!domain) return null
  const index = specialists.findIndex((s) => s.id === domain || (domain === 'product' && s.id === 'service'))
  return index === -1 ? null : { specialist: specialists[index], index }
}

function SpeakerLine({ specialists, domain }: { specialists: Specialist[]; domain: string | null }) {
  const speaker = speakerFor(specialists, domain)
  if (!speaker) return null
  const { specialist, index } = speaker
  return (
    <div className='mb-1 flex items-center gap-2'>
      <img
        src={AvatarImg[index % AvatarImg.length]}
        alt=''
        className={cn('size-6 rounded-full border-2 object-cover', specialist.borderClass)}
      />
      <span className='text-xs font-medium text-foreground'>{specialist.name}</span>
      <span className='truncate text-xs text-muted-foreground'>{specialist.domain} · {specialist.role}</span>
    </div>
  )
}

function isReplying(thread: ChatThread | null): boolean {
  const status = thread?.reply_run?.status
  return status === 'pending' || status === 'running'
}

/**
 * Chat is scoped per workspace: the conversation is stored server-side per
 * workspace, and the agent answers from that workspace's research (plus a
 * quick web lookup when the question needs it). A reply is a server-side run,
 * so it survives navigating away; this view polls while one is in progress.
 */
export function AgentChat({ workspaceId }: { workspaceId?: string }) {
  const { workspaces } = useWorkspaces()
  const specialists = useWorkspaceSpecialists(workspaceId)
  const workspace = workspaceId ? workspaces.find((item) => item.id === workspaceId) : undefined
  const scopeName = workspace ? workspaceDisplayName(workspace) : null

  const [thread, setThread] = useState<ChatThread | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const refresh = useCallback(async () => {
    if (!workspaceId) return
    try {
      setThread(await getChat(workspaceId))
    } catch {
      // keep the last good thread; the next poll retries
    }
  }, [workspaceId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const replying = isReplying(thread)
  useEffect(() => {
    if (!replying) return
    const timer = window.setInterval(() => void refresh(), POLL_MS)
    return () => window.clearInterval(timer)
  }, [replying, refresh])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thread?.messages.length, replying])

  const handleSubmit = async (message: string) => {
    if (!workspaceId || !message) return
    setSending(true)
    setSendError(null)
    try {
      const { message: sent, reply_run } = await sendChat(workspaceId, message)
      setThread((current) => ({ messages: [...(current?.messages ?? []), sent], reply_run }))
    } catch (err) {
      setSendError(err instanceof Error ? err.message : String(err))
    } finally {
      setSending(false)
    }
  }

  const messages = thread?.messages ?? []
  const failedRun = thread?.reply_run?.status === 'failed' ? thread.reply_run : null

  return (
    <div className='flex h-full flex-col'>
      <div className='border-b px-4 py-3'>
        <div className='flex items-center justify-between gap-2'>
          <div>
            <p className='text-base font-medium'>{scopeName} ChatRoom</p>
            <p className='text-sm text-muted-foreground'>Converse with your specialist team.</p>
          </div>
          {specialists.length > 0 && (
            <div className='relative -ml-1.5'>
              <SpecialistAvatarGroup specialists={specialists} />
            </div>
          )}
        </div>
      </div>

      <div className='min-h-0 flex-1 overflow-y-auto px-4 py-4'>
        {messages.length === 0 && !replying ? (
          <div className='flex h-full flex-col items-center justify-center gap-3 text-center'>
            <div className='flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500'>
              <Bot className='size-6' />
            </div>
            <p className='max-w-sm text-sm text-muted-foreground'>
              Ask about your product, market, competitors, customers or outreach. The specialist who owns the
              topic answers you directly, checks with their colleagues when it helps, and grounds the answer
              in {scopeName ? `${scopeName}'s` : 'this workspace’s'} research.
            </p>
          </div>
        ) : (
          <div className='mx-auto flex max-w-3xl flex-col gap-4'>
            {messages.map((m) => (
              <div key={m.id} className={cn('flex flex-col', m.role === 'user' ? 'items-end' : 'items-start')}>
                {m.role === 'assistant' && <SpeakerLine specialists={specialists} domain={m.specialist_domain} />}
                <div
                  className={cn(
                    'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm',
                    m.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted',
                  )}
                >
                  {m.role === 'user' ? (
                    <p className='whitespace-pre-wrap'>{m.content}</p>
                  ) : (
                    <Markdown className='prose prose-sm dark:prose-invert max-w-none'>{m.content}</Markdown>
                  )}
                </div>
              </div>
            ))}
            {replying && (
              <div className='flex items-center gap-2 text-sm text-muted-foreground'>
                <Loader2 className='size-4 animate-spin' /> The right specialist is looking into it…
              </div>
            )}
            {failedRun && (
              <div className='flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive'>
                <AlertTriangle className='mt-0.5 size-4 shrink-0' />
                <span>{failedRun.error ?? 'The reply failed.'} Send your message again to retry.</span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className='border-t p-3'>
        {sendError && <p className='mb-2 text-sm text-destructive'>{sendError}</p>}
        <PromptInputWithActions
          onSubmit={(message) => void handleSubmit(message)}
          isLoading={sending || replying}
          placeholder={replying ? 'Waiting for the reply…' : 'Ask your specialist team…'}
        />
      </div>
    </div>
  )
}
