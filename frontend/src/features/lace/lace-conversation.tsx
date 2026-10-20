import { useEffect, useRef } from "react"
import { AlertTriangle, FileText, Loader2 } from "lucide-react"

import { PromptInputWithActions } from "@/components/chat-input"
import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/ui/markdown"
import { Skeleton } from "@/components/ui/skeleton"
import { DOCUMENT_ACCEPT, type LaceMessageDto } from "@/lib/api"

import { suggestions } from "./chat-suggestions"
import { LaceAvatar } from "./lace-avatar"
import { ChatBlocks } from "./lace-chat-blocks"
import type { LaceChat } from "./use-lace-chat"

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
  return (
    <div className="flex gap-3">
      <LaceAvatar animated={false} />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        {message.content.trim() && (
          <Markdown className="prose prose-sm dark:prose-invert min-w-0 max-w-none">{message.content}</Markdown>
        )}
        {children}
      </div>
    </div>
  )
}

/** The founder's conversation with their Lace: the messages, what it is
 * doing now, the reply as it streams in, and the input. */
export function LaceConversation({ chat, name, onOpenMessaging }: {
  chat: LaceChat
  name: string
  onOpenMessaging: () => void
}) {
  const end = useRef<HTMLDivElement>(null)
  const lastIndex = chat.messages.length - 1
  const ideas = suggestions({
    accounts: chat.accounts, competitors: chat.competitors, outreach: chat.outreach,
    busy: chat.searching || chat.findingAccounts || chat.drafting || chat.findingOpportunities,
  })

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [chat.messages.length, chat.step, chat.draft])

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
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
          {chat.draft && <Message message={{ role: "lace", content: chat.draft }} />}
          {chat.working && !chat.draft && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
              <Loader2 className="size-4 animate-spin" />
              {chat.step ?? (chat.lace?.status === "onboarding" ? "Getting to know your startup" : "Thinking")}
            </div>
          )}
          {chat.error && (
            <div className="flex items-center gap-2 text-sm text-destructive" role="alert">
              <AlertTriangle className="size-4 shrink-0" /> {chat.error}
            </div>
          )}
          <div ref={end} />
        </div>
      </div>
      <div className="flex min-w-0 flex-col items-center gap-2 px-4 py-3">
        {!chat.working && !chat.loading && (
          // One row that scrolls sideways on narrow screens, so it never crowds the chat.
          <div className="flex w-full max-w-3xl gap-2 overflow-x-auto [scrollbar-width:none]" aria-label="Suggestions">
            {ideas.map((idea) => (
              <Button key={idea} size="sm" variant="outline" className="shrink-0 rounded-full" onClick={() => void chat.send(idea)}>
                {idea}
              </Button>
            ))}
          </div>
        )}
        <PromptInputWithActions
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
