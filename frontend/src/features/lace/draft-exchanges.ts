import type { LaceMessageDto } from "@/lib/api"

import type { LaceChat } from "./use-lace-chat"

/** The messages of the conversation about one draft. */
export function aboutDraft(messages: LaceMessageDto[], draftId: string): LaceMessageDto[] {
  return messages.filter((m) => m.draft_id === draftId)
}

/** Whether the Lace is working on the founder's latest message about this draft. */
export function workingOnDraft(chat: Pick<LaceChat, "working" | "messages">, draftId: string): boolean {
  const founder = chat.messages.findLast((m) => m.role === "founder")
  return chat.working && founder?.draft_id === draftId
}

export type ChatItem =
  | { kind: "message"; message: LaceMessageDto; index: number }
  | { kind: "draft"; draftId: string; messages: LaceMessageDto[] }

/** The conversation as the main chat shows it: each run of messages about
 * one draft folded into a single item. */
export function foldDraftExchanges(messages: LaceMessageDto[]): ChatItem[] {
  const items: ChatItem[] = []
  messages.forEach((message, index) => {
    const last = items.at(-1)
    if (!message.draft_id) items.push({ kind: "message", message, index })
    else if (last?.kind === "draft" && last.draftId === message.draft_id) last.messages.push(message)
    else items.push({ kind: "draft", draftId: message.draft_id, messages: [message] })
  })
  return items
}
