import { LaceChannels } from "./lace-channels"
import { LaceContacts } from "./lace-contacts"
import { LaceThreads } from "./lace-threads"
import { LaceSection } from "./lace-section"
import type { LaceChat } from "./use-lace-chat"

/** Reaching out: the messages drafted, sent and received on every channel,
 * the people found at the target accounts, and the business inboxes the
 * Lace reads. */
export function LaceMessaging({ laceId, chat }: { laceId: string; chat: LaceChat }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      <LaceSection title="Conversations" busy={chat.drafting}
                   description="Every message drafted, sent and received, by person. Nothing is sent until you send it.">
        <LaceThreads outreach={chat.outreach} drafting={chat.drafting} actions={{
          sendingSoon: chat.sendingSoon,
          onSave: (id, changes) => void chat.saveDraft(id, changes),
          onDiscard: (id) => void chat.discardDraft(id),
          onSend: chat.sendDraft,
          onUndo: chat.undoSend,
          onMarkSent: (id) => void chat.markSent(id),
        }} />
      </LaceSection>
      <LaceSection title="Contacts" busy={chat.findingAccounts}
                   description="The people your Lace found at your target accounts, and how to reach each.">
        <LaceContacts laceId={laceId} refreshKey={chat.accounts.map((a) => `${a.id}:${a.contact_status}`).join(",")} />
      </LaceSection>
      <LaceSection title="Inboxes" description="Business accounts whose messages your Lace reads and answers.">
        <LaceChannels laceId={laceId} />
      </LaceSection>
    </div>
  )
}
