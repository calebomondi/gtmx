import { useState } from "react"
import { Check, ExternalLink, Loader2, Search, Send, Undo2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import type { CardBlockDto, ChoicesBlockDto, UiBlockDto } from "@/lib/api"

import { cardState, contactsLine, type CardState } from "./chat-cards"
import type { LaceChat } from "./use-lace-chat"

function Choices({ block, live, onChoose }: { block: ChoicesBlockDto; live: boolean; onChoose: (option: string) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium">{block.question}</p>
      <div className="flex flex-wrap gap-2">
        {block.options.map((option) => (
          <Button key={option} size="sm" variant="outline" disabled={!live} onClick={() => onChoose(option)}>
            {option}
          </Button>
        ))}
      </div>
    </div>
  )
}

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
  const [dismissed, setDismissed] = useState(false)
  switch (state.kind) {
    case "competitor":
      return state.tracked ? (
        <>
          <OpenLink url={card.url} />
          <Button size="sm" variant="ghost" onClick={() => void chat.dismissCompetitor(card.id)}><X /> Not a competitor</Button>
        </>
      ) : <Badge variant="secondary">Dismissed</Badge>
    case "account": {
      if (!state.account) return <Badge variant="secondary">Dismissed</Badge>
      const line = contactsLine(state.account)
      return (
        <>
          {line && <span className="text-xs text-muted-foreground">{line}</span>}
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
    case "opportunity":
      return dismissed ? <Badge variant="secondary">Not for us</Badge> : (
        <>
          <OpenLink url={card.url} />
          <Button size="sm" variant="ghost" onClick={() => void chat.dismissOpportunity(card.id).then(setDismissed)}>
            <X /> Not for us
          </Button>
        </>
      )
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

function LaceCard({ card, chat, competitorIds, onReview }: {
  card: CardBlockDto
  chat: LaceChat
  competitorIds: ReadonlySet<string>
  onReview: () => void
}) {
  const state = cardState(card, { competitorIds, accounts: chat.accounts, outreach: chat.outreach })
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

/** The cards and choices under one Lace reply. Choices answer only while
 * this is the latest reply and the Lace is free. */
export function ChatBlocks({ blocks, chat, live, onReview }: {
  blocks: UiBlockDto[]
  chat: LaceChat
  live: boolean
  onReview: () => void
}) {
  const competitorIds = new Set(chat.competitors.map((c) => c.id))
  const cards = blocks.filter((b): b is CardBlockDto => b.type === "card")
  const choices = blocks.filter((b): b is ChoicesBlockDto => b.type === "choices")
  return (
    <div className="flex flex-col gap-3">
      {cards.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {cards.map((card) => (
            <LaceCard key={`${card.kind}:${card.id}`} card={card} chat={chat} competitorIds={competitorIds} onReview={onReview} />
          ))}
        </div>
      )}
      {choices.map((block) => (
        <Choices key={block.question} block={block} live={live && !chat.working} onChoose={(option) => void chat.send(option)} />
      ))}
    </div>
  )
}
