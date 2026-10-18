import { useEffect, useRef, useState } from "react"
import { useParams } from "react-router-dom"
import { AlertTriangle, BookOpen, Loader2, Swords } from "lucide-react"

import { PromptInputWithActions } from "@/components/chat-input"
import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/ui/markdown"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import type { LaceMessageDto } from "@/lib/api"

import { LaceAvatar } from "./lace-avatar"
import { LaceCompetitors } from "./lace-competitors"
import { LaceFacts } from "./lace-facts"
import { useLaceChat } from "./use-lace-chat"

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
      <LaceAvatar />
      <Markdown className="prose prose-sm dark:prose-invert min-w-0 max-w-none">{message.content}</Markdown>
    </div>
  )
}

/** One Lace: its conversation with the founder, what it is doing now, and
 * what it knows. Keyed on the id so moving to another Lace starts fresh. */
export default function LaceChatPage() {
  // The route only renders this page with a lace_id.
  const { lace_id: laceId = "" } = useParams()
  return <LaceChat key={laceId} laceId={laceId} />
}

function LaceChat({ laceId }: { laceId: string }) {
  const chat = useLaceChat(laceId)
  const [panel, setPanel] = useState<"facts" | "competitors" | null>(null)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [chat.messages.length, chat.step, chat.draft])

  const title = chat.lace?.name ?? "Lace"
  const subtitle = chat.lace?.startup_name ?? chat.lace?.website

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <LaceAvatar working={chat.working} />
          <div className="min-w-0">
            <h1 className="truncate text-base font-medium">{title}</h1>
            {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={() => setPanel("competitors")} disabled={chat.loading}>
            {chat.searching ? <Loader2 className="animate-spin" /> : <Swords />}
            <span className="hidden sm:inline">Competitors</span> ({chat.competitors.length})
          </Button>
          <Button variant="outline" size="sm" onClick={() => setPanel("facts")} disabled={chat.loading}>
            <BookOpen /> <span className="hidden sm:inline">What I know</span> ({chat.facts.length})
          </Button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {chat.loading && (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-5 w-1/2" />
            </div>
          )}
          {!chat.loading && chat.messages.length === 0 && !chat.working && (
            <p className="text-sm text-muted-foreground">No messages yet. Say hello to {title}.</p>
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

      <div className="flex justify-center border-t px-4 py-3">
        <PromptInputWithActions
          onSubmit={(text) => void chat.send(text)}
          isLoading={chat.working}
          disabled={chat.loading}
          placeholder={`Message ${title}`}
        />
      </div>

      <Sheet open={panel !== null} onOpenChange={(open) => !open && setPanel(null)}>
        <SheetContent className="overflow-y-auto">
          {panel === "competitors" ? (
            <SheetHeader>
              <SheetTitle>Competitors</SheetTitle>
              <SheetDescription>Companies your buyers could pay instead of you, each checked and profiled from sources.</SheetDescription>
            </SheetHeader>
          ) : (
            <SheetHeader>
              <SheetTitle>What {title} knows</SheetTitle>
              <SheetDescription>Learned from your site, its research and you. Each fact keeps its source.</SheetDescription>
            </SheetHeader>
          )}
          <div className="px-4 pb-6">
            {panel === "competitors" ? (
              <LaceCompetitors competitors={chat.competitors} searching={chat.searching}
                               onDismiss={(id) => void chat.dismissCompetitor(id)} />
            ) : (
              <LaceFacts facts={chat.facts} />
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
