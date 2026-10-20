import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { AlertTriangle, ArrowDown, FileText } from "lucide-react"

import { PromptInputWithActions } from "@/components/chat-input"
import { Markdown } from "@/components/ui/markdown"
import { Skeleton } from "@/components/ui/skeleton"
import { DOCUMENT_ACCEPT, type LaceMessageDto } from "@/lib/api"

import { LaceAvatar } from "./lace-avatar"
import { ChatBlocks } from "./lace-chat-blocks"
import { LaceReplySources } from "./lace-reply-sources"
import { LaceWorkTrail } from "./lace-work-trail"
import { splitSources } from "./reply-sources"
import type { LaceChat } from "./use-lace-chat"
import { useTypewriter } from "./use-typewriter"

/** The reply as it streams in, revealed smoothly with a caret. */
function Streaming({ text }: { text: string }) {
  const shown = useTypewriter(text)
  return (
    <div className="flex gap-3">
      <LaceAvatar state="thinking" />
      <div className="min-w-0 flex-1">
        {/* The sources list is folded under the finished reply, so it never streams in. */}
        <Markdown className="prose prose-sm dark:prose-invert min-w-0 max-w-none">{splitSources(shown).body}</Markdown>
        <span aria-hidden className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-theme align-middle" />
      </div>
    </div>
  )
}

function Message({ message, children }: { message: LaceMessageDto; children?: React.ReactNode }) {
  if (message.role === "founder") {
    return (
      <div className="flex flex-col items-end gap-1.5">
        {message.documents && message.documents.length > 0 && (
          <ul className="flex max-w-[85%] flex-wrap justify-end gap-1.5" aria-label="Attached">
            {message.documents.map((doc) => (
              <li key={doc.id} className="flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1.5 text-xs">
                <FileText className="size-3.5 text-theme" /> <span className="max-w-48 truncate">{doc.filename}</span>
              </li>
            ))}
          </ul>
        )}
        {message.content && (
          <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-muted px-4 py-2 text-sm">{message.content}</div>
        )}
      </div>
    )
  }
  const { body, sources } = splitSources(message.content)
  return (
    <div className="flex gap-3">
      <LaceAvatar animated={false} />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        {body.trim() && (
          <Markdown className="prose prose-sm dark:prose-invert min-w-0 max-w-none">{body}</Markdown>
        )}
        {children}
        <LaceReplySources sources={sources} />
      </div>
    </div>
  )
}

// Within this distance of the end counts as reading the latest.
const LATEST_SLACK_PX = 120

/** The founder's conversation with their Lace: the messages, what it is
 * doing now, the reply as it streams in, and the input. Scrolled back, a
 * button returns to the latest and counts what arrived meanwhile. */
export function LaceConversation({ chat, name, onOpenMessaging, dock, prefill }: {
  chat: LaceChat
  name: string
  onOpenMessaging: () => void
  /** Shown above the input: what the Lace has found so far. */
  dock?: React.ReactNode
  /** A message waiting in the input ("Discuss with…"), for the founder to edit or send. */
  prefill?: { key: string; text: string }
}) {
  const end = useRef<HTMLDivElement>(null)
  const lastIndex = chat.messages.length - 1
  // Whether the founder is reading the latest, and how many messages there
  // were when they scrolled up: what arrived since is "new".
  const [atLatest, setAtLatest] = useState(true)
  const [countWhenLeft, setCountWhenLeft] = useState(0)
  const unseen = atLatest ? 0 : Math.max(0, chat.messages.length - countWhenLeft)
  const lastIsFounder = chat.messages[lastIndex]?.role === "founder"
  const toLatest = () => end.current?.scrollIntoView({ behavior: "smooth", block: "end" })

  // Follow the conversation while they are at the latest, and always when
  // they have just sent something; never pull them down while they read back.
  useEffect(() => {
    if (atLatest || lastIsFounder) end.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [chat.messages.length, chat.steps.length, chat.draft, atLatest, lastIsFounder])

  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < LATEST_SLACK_PX
    if (near !== atLatest) {
      setAtLatest(near)
      if (!near) setCountWhenLeft(chat.messages.length)
    }
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="relative flex min-h-0 flex-1 flex-col">
      <AnimatePresence>
        {!atLatest && (
          <motion.button type="button" onClick={toLatest} aria-label={unseen ? `${unseen} new messages, go to latest` : "Go to latest"}
                         initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
                         className="absolute bottom-3 left-1/2 z-10 flex -translate-x-1/2 cursor-pointer items-center gap-1.5 rounded-full border bg-background/90 px-3 py-1.5 text-xs shadow-md backdrop-blur hover:border-theme/50">
            <ArrowDown className="size-3.5" />
            {unseen > 0 ? <><span className="font-medium">{unseen} new</span> · Latest</> : "Latest"}
          </motion.button>
        )}
      </AnimatePresence>
      <div className="min-h-0 flex-1 overflow-y-auto" onScroll={onScroll}>
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {chat.loading && (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-5 w-1/2" />
            </div>
          )}
          {!chat.loading && chat.messages.length === 0 && !chat.working && (
            <p className="text-sm text-muted-foreground">No messages yet. Say hello to {name}.</p>
          )}
          {chat.messages.map((message, i) => (
            <Message key={i} message={message}>
              {message.ui && message.ui.length > 0 && (
                <ChatBlocks blocks={message.ui} chat={chat} live={i === lastIndex} onReview={onOpenMessaging} />
              )}
            </Message>
          ))}
          {chat.draft && <Streaming text={chat.draft} />}
          {chat.working && !chat.draft && (
            <LaceWorkTrail steps={chat.steps}
                           fallback={chat.lace?.status === "onboarding" ? "Getting to know your startup" : "Thinking"} />
          )}
          {chat.error && (
            <div className="flex items-center gap-2 text-sm text-destructive" role="alert">
              <AlertTriangle className="size-4 shrink-0" /> {chat.error}
            </div>
          )}
          <div ref={end} />
        </div>
      </div>
      </div>
      <div className="flex min-w-0 flex-col items-center gap-2 px-4 py-3">
        {dock}
        <PromptInputWithActions
          // A new topic remounts the input with its text in place.
          key={prefill?.key ?? "chat"}
          defaultValue={prefill?.text}
          onSubmit={(text, files) => void chat.send(text, files)}
          accept={DOCUMENT_ACCEPT}
          isLoading={chat.working}
          disabled={chat.loading}
          placeholder={`Message ${name}`}
        />
      </div>
    </div>
  )
}
