import { AtSign, Inbox, PenLine, Reply, Send, Users, type LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

import { MESSAGING_SECTIONS, type MessagingSection } from "./lace-activity-actions"
import { LaceChannels } from "./lace-channels"
import { LaceContacts } from "./lace-contacts"
import { LacePanelTabs, PanelIntro, type PanelTab } from "./lace-panel-tabs"
import { LaceThreads } from "./lace-threads"
import { outreachTally } from "./outreach-threads"
import type { LaceChat } from "./use-lace-chat"
import { useSection } from "./use-lace-section"

function Stat({ icon: Icon, value, label, highlight = false }: {
  icon: LucideIcon
  value: number
  label: string
  highlight?: boolean
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border bg-background/60 px-3 py-2.5">
      {/* Phones keep the number and label only, so three fit in a row. */}
      <span className={cn("hidden size-8 place-items-center rounded-full sm:grid",
                          highlight ? "bg-theme text-neutral-900" : "bg-muted text-muted-foreground")}>
        <Icon className="size-4" />
      </span>
      <span className="flex flex-col">
        <span className="text-lg leading-tight font-semibold tabular-nums">{value}</span>
        <span className="text-xs text-muted-foreground">{label}</span>
      </span>
    </div>
  )
}

/** Reaching out, as sub-tabs: the conversations on every channel (an inbox
 * of drafts, sends and replies), the people found at target accounts, and
 * the business inboxes the Lace reads. A short tally sits on top. */
export function LaceMessaging({ laceId, name, chat }: { laceId: string; name: string; chat: LaceChat }) {
  const [section, setSection] = useSection<MessagingSection>(MESSAGING_SECTIONS)
  const tally = outreachTally(chat.outreach)
  const toApprove = chat.contacts.filter((c) => !c.approved_at).length

  const tabs: PanelTab<MessagingSection>[] = [
    {
      value: "conversations", label: "Conversations", icon: Inbox, waiting: chat.waiting, busy: chat.drafting,
      content: (
        <>
          <PanelIntro>Every message drafted, sent and received, by person. Nothing goes out until you send it.</PanelIntro>
          <LaceThreads outreach={chat.outreach} drafting={chat.drafting} actions={{
            sendingSoon: chat.sendingSoon,
            onSave: (id, changes) => void chat.saveDraft(id, changes),
            onDiscard: (id) => void chat.discardDraft(id),
            onSend: chat.sendDraft,
            onUndo: chat.undoSend,
            onMarkSent: (id) => void chat.markSent(id),
          }} />
        </>
      ),
    },
    {
      value: "people", label: "People", icon: Users, count: chat.contacts.length, waiting: toApprove,
      busy: chat.findingAccounts,
      content: (
        <>
          <PanelIntro>
            The people {name} found at your saved accounts. It drafts only to people you approve.
          </PanelIntro>
          <LaceContacts contacts={chat.contacts} onApprove={(id, approved) => void chat.approveContact(id, approved)}
                        onApproveAccount={(id) => void chat.approveAccountContacts(id)} />
        </>
      ),
    },
    {
      value: "inboxes", label: "Inboxes", icon: AtSign,
      content: (
        <>
          <PanelIntro>Business accounts whose messages {name} reads and answers for you to approve.</PanelIntro>
          <LaceChannels laceId={laceId} />
        </>
      ),
    },
  ]

  return (
    <LacePanelTabs label={`${name}'s Messaging`} tabs={tabs} value={section} onChange={setSection} header={
      <section aria-label="Outreach so far" className="grid grid-cols-3 gap-2">
        <Stat icon={PenLine} value={tally.drafts} label="Drafts to send" highlight={tally.drafts > 0} />
        <Stat icon={Send} value={tally.sent} label="Sent" />
        <Stat icon={Reply} value={tally.replies} label="Replies" highlight={chat.waiting > tally.drafts} />
      </section>
    } />
  )
}
