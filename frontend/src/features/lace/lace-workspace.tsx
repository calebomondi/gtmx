import { useState } from "react"
import { Navigate, useNavigate, useParams } from "react-router-dom"
import { RotateCcw, Settings2 } from "lucide-react"

import { Button } from "@/components/ui/button"

import { sectionHash, type FeedTarget } from "./lace-activity-actions"
import { LaceConversation } from "./lace-conversation"
import { LaceFeed } from "./lace-feed"
import { LaceMessaging } from "./lace-messaging"
import { LaceRail, LaceTabBar } from "./lace-rail"
import { chatMascot, LACE_TABS, type LaceTab } from "./lace-tabs"
import { LaceSettings } from "./lace-settings"
import { LaceStatusBanner } from "./lace-status-banner"
import { useLaceActivity } from "./use-lace-activity"
import { useLaceChat } from "./use-lace-chat"

function isTab(value: string | undefined): value is LaceTab {
  return LACE_TABS.includes(value as LaceTab)
}

/** One Lace: Feed, the chat and Messaging, reached from three round buttons.
 * It opens on Feed. Keyed on the Lace id, so moving to another Lace starts
 * fresh. */
export default function LaceWorkspacePage() {
  // The route only renders this page with a lace_id.
  const { lace_id: laceId = "", tab } = useParams()
  if (tab !== undefined && !isTab(tab)) return <Navigate to={`/lace/${laceId}`} replace />
  return <LaceWorkspace key={laceId} laceId={laceId} tab={tab ?? "feed"} />
}

function LaceWorkspace({ laceId, tab }: { laceId: string; tab: LaceTab }) {
  const navigate = useNavigate()
  // One load of the Lace serves all three tabs, so the chat keeps following
  // its run while the founder looks at the Feed.
  const chat = useLaceChat(laceId)
  const activity = useLaceActivity(laceId, tab === "feed")
  const [settingsOpen, setSettingsOpen] = useState(false)
  const name = chat.lace?.name ?? "Lace"
  const subtitle = chat.lace?.startup_name ?? chat.lace?.website
  const select = (next: LaceTab) => navigate(`/lace/${laceId}/${next}`)
  // The sub-tab rides in the hash, which Feed and Messaging read.
  const open = ({ tab: next, section }: FeedTarget) =>
    navigate(`/lace/${laceId}/${next}${section ? sectionHash(section) : ""}`)
  const nav = {
    tab,
    onSelect: select,
    name,
    mascot: chatMascot(tab, chat.working),
    waiting: chat.waiting,
    unread: activity.unread,
    feedBusy: chat.searching || chat.findingAccounts || chat.findingOpportunities,
    messagingBusy: chat.drafting,
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-base font-medium">{name}</h1>
          {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        <Button variant="outline" size="icon-sm" onClick={() => setSettingsOpen(true)} disabled={chat.loading}
                aria-label={`${name}'s settings`} title="Settings">
          <Settings2 />
        </Button>
      </header>
      <LaceStatusBanner lace={chat.lace} working={chat.working} onChanged={() => void chat.reload()} />
      {/* The chat shows its own errors in line; elsewhere they sit up here. */}
      {tab !== "chat" && chat.error && (
        <div role="alert" className="flex items-center justify-between gap-2 border-b bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <span>Couldn't load everything: {chat.error}</span>
          <Button size="sm" variant="outline" onClick={() => void chat.reload()}><RotateCcw /> Retry</Button>
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        {/* Its own column beside the content, centred top to bottom. */}
        <aside className="hidden w-[4.5rem] shrink-0 items-center justify-center border-r md:flex">
          <LaceRail {...nav} />
        </aside>
        <main className={tab === "chat" ? "flex min-h-0 min-w-0 flex-1 flex-col" : "min-h-0 min-w-0 flex-1 overflow-y-auto"}>
          {tab === "chat" && <LaceConversation chat={chat} name={name} onOpenMessaging={() => select("messaging")} />}
          {tab === "feed" && <LaceFeed laceId={laceId} name={name} chat={chat} activity={activity} onOpen={open} />}
          {tab === "messaging" && <LaceMessaging laceId={laceId} name={name} chat={chat} />}
        </main>
      </div>
      <LaceTabBar {...nav} className="md:hidden" />
      <LaceSettings laceId={laceId} name={name} status={chat.lace?.status ?? "active"} facts={chat.facts}
                    open={settingsOpen} onOpenChange={setSettingsOpen} onChanged={() => void chat.reload()} />
    </div>
  )
}
