import { useEffect, useRef } from "react"
import { AlertTriangle, Loader2 } from "lucide-react"

import { PromptInputWithActions } from "@/components/chat-input"
import { Markdown } from "@/components/ui/markdown"
import { Skeleton } from "@/components/ui/skeleton"
import type { LaceMessageDto } from "@/lib/api"

import { LaceAvatar } from "./lace-avatar"
import type { LaceChat } from "./use-lace-chat"

function Message({ message }: { message: LaceMessageDto }) {
  if (message.role === "founder") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-muted px-4 py-2 text-sm">{message.content}</div>
      </div>
    )
  }
  return (
    <div className="flex gap-3">
      <LaceAvatar animated={false} />
      <Markdown className="prose prose-sm dark:prose-invert min-w-0 max-w-none">{message.content}</Markdown>
    </div>
  )
}

/** The founder's conversation with their Lace: the messages, what it is
 * doing now, the reply as it streams in, and the input. */
export function LaceConversation({ chat, name }: { chat: LaceChat; name: string }) {
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [chat.messages.length, chat.step, chat.draft])

  return (
    <div className="flex min-h-0 flex-1 flex-col">
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
          {chat.messages.map((message, i) => <Message key={i} message={message} />)}
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
      <div className="flex justify-center px-4 py-3">
        <PromptInputWithActions
          onSubmit={(text) => void chat.send(text)}
          isLoading={chat.working}
          disabled={chat.loading}
          placeholder={`Message ${name}`}
        />
      </div>
    </div>
  )
}
