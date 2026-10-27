import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { AlertTriangle, ArrowDown, ChevronRight, Clock, FileText, PenLine } from "lucide-react"

import { PromptInputWithActions } from "@/components/chat-input"
import { Skeleton } from "@/components/ui/skeleton"
import { DOCUMENT_ACCEPT, type ChatThread, type LaceMessageDto } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"

import { ChatThreadSwitch } from "./chat-thread-switch"
import { LaceAvatar } from "./lace-avatar"
import { ChatBlocks } from "./lace-chat-blocks"
import { LaceReplySources } from "./lace-reply-sources"
import { LaceWorkTrail } from "./lace-work-trail"
import { PersonAvatar } from "./person-avatar"
import { foldDraftExchanges } from "./draft-exchanges"
import { answersByBlock } from "./questions"
import { splitSources } from "./reply-sources"
import type { LaceChat } from "./use-lace-chat"
import { useTypewriter } from "./use-typewriter"
import { ReplyMarkdown } from "./reply-markdown"

/** The reply as it streams in, revealed smoothly with a caret. */
function Streaming({ text }: { text: string }) {
  const shown = useTypewriter(text)
  return (
    <div className="flex gap-3">
      <LaceAvatar state="thinking" />
      <div className="min-w-0 flex-1">
        {/* The sources list is folded under the finished reply, so it never streams in. */}
        <ReplyMarkdown>{splitSources(shown).body}</ReplyMarkdown>
        <span aria-hidden className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-theme align-middle" />
      </div>
    </div>
  )
}

/** A brainstorm about one draft, which happened beside the draft: one line
 * here, opening to the exchange. */
function DraftExchange({ messages, to }: { messages: LaceMessageDto[]; to: string | null }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex flex-col gap-3">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
              className="flex cursor-pointer items-center gap-2 self-center rounded-full border border-dashed px-3 py-1 text-xs text-muted-foreground hover:border-theme/50 hover:text-foreground">
        <PenLine className="size-3.5" /> Worked on the draft{to ? ` to ${to}` : ""} · {messages.length} messages
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
      </button>
      {open && messages.map((m, i) => <Message key={i} message={m} />)}
    </div>
  )
}

/** Who sent a founder message: its author, else (just sent, not yet saved) the person here. */
interface Sender { name: string | null; email: string | null; avatarUrl: string | null }

function Message({ message, sender, children }: {
  message: LaceMessageDto
  /** Shown beside the founder's message when the Lace has a team. */
  sender?: Sender
  children?: React.ReactNode
}) {
  if (message.role === "founder") {
    const bubble = (
      <div className="flex min-w-0 flex-col items-end gap-1.5">
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
          <div className={cn("max-w-[85%] whitespace-pre-wrap rounded-2xl bg-muted px-4 py-2 text-sm",
                             message.queued && "opacity-60")}>{message.content}</div>
        )}
        {message.queued && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="size-3" /> Waiting its turn
          </span>
        )}
      </div>
    )
    if (!sender) return bubble
    return (
      <div className="flex justify-end gap-3">
        <div className="flex min-w-0 flex-1 flex-col items-end">{bubble}</div>
        <PersonAvatar name={sender.name} email={sender.email} avatarUrl={sender.avatarUrl} />
      </div>
    )
  }
  const { body, sources } = splitSources(message.content)
  return (
    <div className="flex gap-3">
      <LaceAvatar animated={false} />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        {body.trim() && (
          <ReplyMarkdown>{body}</ReplyMarkdown>
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
export function LaceConversation({ chat, name, onOpenMessaging, dock, prefill, starters, team = false, talking, thread,
                                   onThread }: {
  chat: LaceChat
  name: string
  onOpenMessaging: () => void
  /** Shown above the input: what the Lace has found so far. */
  dock?: React.ReactNode
  /** A message waiting in the input ("Discuss with…"), for the founder to edit or send. */
  prefill?: { key: string; text: string }
  /** Shown while there is no conversation yet: things to ask. */
  starters?: React.ReactNode
  /** The Lace has several people: each founder message shows who sent it. */
  team?: boolean
  /** Someone else on the team the Lace is answering now: a message sent meanwhile waits its turn. */
  talking?: string | null
  /** On a Lace with a team: which chat this is, and the switch to the other. */
  thread?: ChatThread
  onThread?: (next: ChatThread) => void
}) {
  const alone = thread === "mine"
  const { user } = useAuth()
  const senderOf = (message: LaceMessageDto): Sender | undefined => {
    if (!team || message.role !== "founder") return undefined
    if (message.author) return { name: message.author.name, email: null, avatarUrl: message.author.avatar_url }
    const meta = user?.user_metadata ?? {}
    return { name: meta.full_name ?? meta.name ?? null, email: user?.email ?? null,
             avatarUrl: meta.avatar_url ?? meta.picture ?? null }
  }
  const end = useRef<HTMLDivElement>(null)
  // Messages waiting their turn come after what the Lace is doing now, and
  // the latest reply's questions stay live under it.
  const said = chat.messages.filter((m) => !m.queued)
  const waiting = chat.messages.filter((m) => m.queued)
  const lastIndex = said.length - 1
  const answers = answersByBlock(said)
  // Whether the founder is reading the latest, and how many messages there
  // were when they scrolled up: what arrived since is "new".
  const [atLatest, setAtLatest] = useState(true)
  const [countWhenLeft, setCountWhenLeft] = useState(0)
  const unseen = atLatest ? 0 : Math.max(0, chat.messages.length - countWhenLeft)
  const lastIsFounder = chat.messages[chat.messages.length - 1]?.role === "founder"
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
          {/* A child of the scrolling column itself, so it stays in view
              while the messages pass under it. */}
          {thread && onThread && (
            <div className="sticky top-2 z-10 -mb-4 flex justify-center">
              <ChatThreadSwitch value={thread} onChange={onThread} />
            </div>
          )}
          {thread && onThread && alone && (
            <p className="mx-auto max-w-md text-center text-xs text-muted-foreground">
              Only you see this chat. What {name} finds here stays yours until you share it with the team.
            </p>
          )}
          {chat.loading && (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-5 w-1/2" />
            </div>
          )}
          {!chat.loading && chat.messages.length === 0 && !chat.working && (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">No messages yet. Say hello to {name}.</p>
              {starters}
            </div>
          )}
          {foldDraftExchanges(said).map((item, i) => item.kind === "draft" ? (
            <DraftExchange key={`draft:${i}`} messages={item.messages}
                           to={chat.outreach.find((m) => m.id === item.draftId)?.recipient_name ?? null} />
          ) : (
            <Message key={item.index} message={item.message} sender={alone ? undefined : senderOf(item.message)}>
              {item.message.ui && item.message.ui.length > 0 && (
                <ChatBlocks blocks={item.message.ui} chat={chat} live={item.index === lastIndex} answers={answers}
                            onReview={onOpenMessaging} />
              )}
            </Message>
          ))}
          {chat.draft && <Streaming text={chat.draft} />}
          {chat.working && !chat.draft && (
            <LaceWorkTrail steps={chat.steps}
                           fallback={chat.lace?.status === "onboarding" ? "Getting to know your startup"
                             : talking ? `Answering ${talking}` : "Thinking"} />
          )}
          {waiting.map((message, i) => (
            <Message key={`waiting:${i}`} message={message} sender={senderOf(message)} />
          ))}
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
        {chat.working && talking && (
          <p className="text-xs text-muted-foreground">
            {talking} is talking to {name}. Anything you send waits its turn.
          </p>
        )}
        <PromptInputWithActions
          // A new topic remounts the input with its text in place.
          key={prefill?.key ?? "chat"}
          defaultValue={prefill?.text}
          onSubmit={(text, files) => void chat.send(text, files)}
          accept={DOCUMENT_ACCEPT}
          isLoading={chat.working && !talking}
          disabled={chat.loading}
          placeholder={alone ? `Message ${name}, just between you` : `Message ${name}`}
        />
      </div>
    </div>
  )
}
