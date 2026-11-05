import type { LaceAppDto } from "@/lib/api"

import { DraftBrainstorm } from "./draft-brainstorm"
import type { ThreadActions } from "./lace-threads"
import type { LaceChat } from "./use-lace-chat"

/** What a conversation's buttons do: the same in Outreach and in Social's
 * messages. `mailboxes`: the Lace's connected ones, for a new email's sender. */
export function threadActions(chat: LaceChat, name: string, mailboxes: LaceAppDto[] = []): ThreadActions {
  return {
    sendingSoon: chat.sendingSoon,
    onSave: (id, changes) => void chat.saveDraft(id, changes),
    onDiscard: (id) => void chat.discardDraft(id),
    onSend: chat.sendDraft,
    onUndo: chat.undoSend,
    onMarkSent: (id) => void chat.markSent(id),
    onRead: chat.markRead,
    brainstorm: (draft) => <DraftBrainstorm draft={draft} chat={chat} name={name} />,
    mailboxes,
  }
}
