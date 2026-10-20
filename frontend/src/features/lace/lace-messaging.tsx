import { useSearchParams } from "react-router-dom"
import { Inbox, PenLine, Reply, Send, Users, type LucideIcon } from "lucide-react"

import type { OutreachChannel } from "@/lib/api"

import { MESSAGING_SECTIONS, type MessagingSection } from "./lace-activity-actions"
import { LaceAccountSwitcher } from "./lace-account-switcher"
import { LaceContacts } from "./lace-contacts"
import { LacePanelTabs, PanelIntro, type PanelTab } from "./lace-panel-tabs"
import { LaceThreads, type ThreadActions } from "./lace-threads"
import { messagingAccounts, onAccount, type AccountKey } from "./messaging-accounts"
import { groupThreads, inFolder, outreachTally, waitsOnFounder } from "./outreach-threads"
import type { LaceChat } from "./use-lace-chat"
import { useConnections } from "./use-connections"
import { useSection } from "./use-lace-section"

function Stat({ icon: Icon, value, label }: { icon: LucideIcon; value: number; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-background/60 px-2.5 py-1.5">
      <Icon className="hidden size-3.5 text-theme sm:block" />
      <span className="font-semibold tabular-nums">{value}</span>
      <span className="truncate text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

/** Reaching out. A header in the theme colour picks the account (all, or
 * one connected account, with a way to connect more) and tallies it; under
 * it, sub-tabs for that account's conversations (everything someone
 * answered), drafts to send, what was sent and awaits an answer, and the
 * contacts the Lace found. */
export function LaceMessaging({ laceId, name, chat }: { laceId: string; name: string; chat: LaceChat }) {
  const [section, setSection] = useSection<MessagingSection>(MESSAGING_SECTIONS)
  const [params, setParams] = useSearchParams()
  const connections = useConnections()
  const accounts = messagingAccounts(connections.connections, chat.outreach)
  const requested = params.get("account")
  const account: AccountKey = accounts.some((a) => a.key === requested) ? (requested as OutreachChannel) : "all"
  const selectAccount = (next: AccountKey) => setParams((prev) => {
    if (next === "all") prev.delete("account")
    else prev.set("account", next)
    return prev
  }, { replace: true })

  const outreach = onAccount(chat.outreach, account)
  const tally = outreachTally(outreach)
  const threads = groupThreads(outreach)
  const count = (folder: Parameters<typeof inFolder>[1]) => threads.filter((t) => inFolder(t, folder)).length
  const unreadReplies = outreach.filter((m) => m.direction === "inbound" && waitsOnFounder(m)).length
  const toApprove = chat.contacts.filter((c) => !c.approved_at).length
  const actions: ThreadActions = {
    sendingSoon: chat.sendingSoon,
    onSave: (id, changes) => void chat.saveDraft(id, changes),
    onDiscard: (id) => void chat.discardDraft(id),
    onSend: chat.sendDraft,
    onUndo: chat.undoSend,
    onMarkSent: (id) => void chat.markSent(id),
  }
  const inbox = (folder: "replies" | "drafts" | "awaiting", empty: { title: string; body: string }) => (
    <LaceThreads outreach={outreach} folder={folder} drafting={chat.drafting} actions={actions} empty={empty} />
  )

  const tabs: PanelTab<MessagingSection>[] = [
    {
      value: "conversations", label: "Conversations", icon: Inbox, count: count("replies"), waiting: unreadReplies,
      content: (
        <>
          <PanelIntro>Everyone who answered, newest first: read their reply and the draft {name} wrote back.</PanelIntro>
          {inbox("replies", { title: "No replies yet", body: "When someone answers a message you sent, the conversation shows here." })}
        </>
      ),
    },
    {
      value: "drafts", label: "Drafts", icon: PenLine, waiting: tally.drafts, busy: chat.drafting,
      content: (
        <>
          <PanelIntro>Messages {name} wrote for you. Edit any of them; nothing goes out until you send it.</PanelIntro>
          {inbox("drafts", { title: "No drafts", body: `Approve people under Contacts, then ask ${name} to draft outreach to them.` })}
        </>
      ),
    },
    {
      value: "sent", label: "Sent", icon: Send, count: count("awaiting"),
      content: (
        <>
          <PanelIntro>Sent and waiting for an answer. Once someone replies, they move to Conversations.</PanelIntro>
          {inbox("awaiting", { title: "Nothing waiting on an answer", body: "Messages you send show here until someone replies." })}
        </>
      ),
    },
    {
      value: "contacts", label: "Contacts", icon: Users, count: chat.contacts.length, waiting: toApprove,
      busy: chat.findingAccounts,
      content: (
        <>
          <PanelIntro>The people {name} found at your saved accounts, in the chat or its searches. It drafts only to people you approve.</PanelIntro>
          <LaceContacts contacts={chat.contacts} onApprove={(id, approved) => void chat.approveContact(id, approved)}
                        onApproveAccount={(id) => void chat.approveAccountContacts(id)} />
        </>
      ),
    },
  ]

  return (
    <LacePanelTabs label={`${name}'s Messaging`} tabs={tabs} value={section} onChange={setSection} header={
      <section aria-label="Accounts" className="flex flex-col gap-3 rounded-2xl border bg-gradient-to-br from-theme/12 via-card to-card p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <h2 className="text-base font-medium">Messaging</h2>
          <p className="text-xs text-muted-foreground">Nothing is sent until you send it</p>
        </div>
        <LaceAccountSwitcher laceId={laceId} name={name} accounts={accounts} value={account} onChange={selectAccount}
                             totalWaiting={chat.waiting} connections={connections} />
        <div className="grid grid-cols-3 gap-2">
          <Stat icon={PenLine} value={tally.drafts} label="To send" />
          <Stat icon={Send} value={tally.sent} label="Sent" />
          <Stat icon={Reply} value={tally.replies} label="Replies" />
        </div>
      </section>
    } />
  )
}
