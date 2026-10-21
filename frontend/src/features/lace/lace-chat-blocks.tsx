import { useState } from "react"
import { Bookmark, Check, CheckCheck, ExternalLink, Loader2, Search, Send, Undo2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import type { BlockAnswerDto, CardBlockDto, UiBlockDto } from "@/lib/api"

import { cardState, contactsLine, type CardState } from "./chat-cards"
import { ChatQuestion } from "./lace-chat-questions"
import { isQuestion } from "./questions"
import { waitingAt } from "./contacts-model"
import type { LaceChat } from "./use-lace-chat"

function OpenLink({ url }: { url: string | null }) {
  if (!url) return null
  return (
    <a href={url} target="_blank" rel="noreferrer" className={buttonVariants({ size: "sm", variant: "ghost" })}>
      <ExternalLink /> Open
    </a>
  )
}

function Actions({ card, state, chat, onReview }: {
  card: CardBlockDto
  state: CardState
  chat: LaceChat
  onReview: () => void
}) {
  const [decided, setDecided] = useState<"open" | "dismissed" | null>(null)
  switch (state.kind) {
    case "competitor":
      if (state.standing === "gone") return <Badge variant="secondary">Dismissed</Badge>
      return (
        <>
          {state.standing === "suggested" && (
            <Button size="sm" onClick={() => void chat.saveCompetitor(card.id)}><Bookmark /> Track</Button>
          )}
          <OpenLink url={card.url} />
          <Button size="sm" variant="ghost" onClick={() => void chat.dismissCompetitor(card.id)}><X /> Not a competitor</Button>
        </>
      )
    case "account": {
      if (state.standing === "gone" || !state.account) return <Badge variant="secondary">Dismissed</Badge>
      if (state.standing === "suggested") {
        return (
          <>
            <Button size="sm" onClick={() => void chat.saveAccount(card.id)}><Bookmark /> Save</Button>
            <Button size="sm" variant="ghost" onClick={() => void chat.dismissAccount(card.id)}><X /> Dismiss</Button>
          </>
        )
      }
      const line = contactsLine(state.account)
      const waiting = waitingAt(chat.contacts, card.id)
      return (
        <>
          {line && <span className="text-xs text-muted-foreground">{line}</span>}
          {waiting > 0 && (
            <Button size="sm" onClick={() => void chat.approveAccountContacts(card.id)}>
              <CheckCheck /> Approve {waiting === 1 ? "1 person" : `${waiting} people`}
            </Button>
          )}
          {chat.findingAccounts ? (
            <Button size="sm" variant="outline" disabled><Loader2 className="animate-spin" /> Looking…</Button>
          ) : (
            <Button size="sm" variant="outline" onClick={() => void chat.findContacts(card.id)}>
              <Search /> {state.account.contacts_checked_at ? "Look again" : "Find contacts"}
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => void chat.dismissAccount(card.id)}><X /> Dismiss</Button>
        </>
      )
    }
    case "opportunity": {
      const decide = (status: "open" | "dismissed") =>
        void chat.decideOpportunity(card.id, status).then((done) => done && setDecided(status))
      // What was decided here, else where it stood when the chat was loaded.
      const standing = decided ?? card.status
      if (standing === "open") return <Badge variant="secondary"><Check /> Saved</Badge>
      if (standing === "dismissed") return <Badge variant="secondary">Not for us</Badge>
      if (standing === "gone") return <Badge variant="secondary">Removed</Badge>
      return (
        <>
          <Button size="sm" onClick={() => decide("open")}><Bookmark /> Save</Button>
          <OpenLink url={card.url} />
          <Button size="sm" variant="ghost" onClick={() => decide("dismissed")}><X /> Not for us</Button>
        </>
      )
    }
    case "draft": {
      const message = state.message
      if (!message) return <Badge variant="secondary">Discarded</Badge>
      if (message.status === "sent") return <Badge variant="secondary"><Check /> Sent</Badge>
      if (chat.sendingSoon.has(message.id)) {
        return (
          <>
            <span className="text-xs text-muted-foreground" aria-live="polite">Sending…</span>
            <Button size="sm" variant="outline" onClick={() => chat.undoSend(message.id)}><Undo2 /> Undo</Button>
          </>
        )
      }
      // Email and X go from here; the other channels are sent by hand from Messaging.
      const direct = message.channel === "email" || message.channel === "x"
      return (
        <>
          <Button size="sm" variant="outline" onClick={onReview}>Review</Button>
          {direct && message.status === "draft" && message.recipient_address && (
            <Button size="sm" onClick={() => chat.sendDraft(message.id)}><Send /> Send</Button>
          )}
        </>
      )
    }
  }
}

function LaceCard({ card, chat, ids, onReview }: {
  card: CardBlockDto
  chat: LaceChat
  ids: { saved: ReadonlySet<string>; suggested: ReadonlySet<string> }
  onReview: () => void
}) {
  const state = cardState(card, {
    competitorIds: ids.saved, suggestedCompetitorIds: ids.suggested, accounts: chat.accounts,
    suggestedAccounts: chat.suggestedAccounts, outreach: chat.outreach,
  })
  return (
    <Card size="sm" className="gap-2">
      <CardHeader>
        <CardTitle className="text-sm">{card.title}</CardTitle>
        {card.subtitle && <CardDescription className="truncate">{card.subtitle}</CardDescription>}
      </CardHeader>
      {card.body && <CardContent className="line-clamp-4 text-sm whitespace-pre-line text-muted-foreground">{card.body}</CardContent>}
      <CardFooter className="flex-wrap gap-2">
        <Actions card={card} state={state} chat={chat} onReview={onReview} />
      </CardFooter>
    </Card>
  )
}

/** The cards and questions under one Lace reply. A question can be answered
 * only while this is the latest reply and the Lace is free; once answered it
 * shows the answer. */
export function ChatBlocks({ blocks, chat, live, answers, onReview }: {
  blocks: UiBlockDto[]
  chat: LaceChat
  live: boolean
  /** The conversation's answers, by question id. */
  answers: ReadonlyMap<string, BlockAnswerDto>
  onReview: () => void
}) {
  const ids = {
    saved: new Set(chat.competitors.map((c) => c.id)),
    suggested: new Set(chat.suggestedCompetitors.map((c) => c.id)),
  }
  const cards = blocks.filter((b): b is CardBlockDto => b.type === "card")
  const questions = blocks.filter(isQuestion)
  return (
    <div className="flex flex-col gap-3">
      {cards.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {cards.map((card) => (
            <LaceCard key={`${card.kind}:${card.id}`} card={card} chat={chat} ids={ids} onReview={onReview} />
          ))}
        </div>
      )}
      {questions.map((block) => (
        <ChatQuestion key={block.id ?? block.question} block={block} answer={block.id ? answers.get(block.id) : undefined}
                      live={live && !chat.working} onAnswer={(answer) => void chat.answer(block, answer)} />
      ))}
    </div>
  )
}
