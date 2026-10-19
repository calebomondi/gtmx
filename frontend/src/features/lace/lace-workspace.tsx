import { useEffect, useState } from "react"
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom"
import { Settings2 } from "lucide-react"

import { Button } from "@/components/ui/button"

import { sectionId, type FeedTarget } from "./lace-activity-actions"
import { LaceConversation } from "./lace-conversation"
import { LaceFeed } from "./lace-feed"
import { LaceMessaging } from "./lace-messaging"
import { LaceRail, LaceTabBar } from "./lace-rail"
import { chatMascot, LACE_TABS, type LaceTab } from "./lace-tabs"
import { LaceSettings } from "./lace-settings"
import { useLaceActivity } from "./use-lace-activity"
import { useLaceChat } from "./use-lace-chat"

// Long enough for a tab's content to mount before scrolling to a section in it.
const SECTION_SCROLL_DELAY_MS = 100

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
  const { hash } = useLocation()

  // A link to a Feed section (from Home) scrolls there once the tab is in.
  useEffect(() => {
    if (!hash) return
    const timer = window.setTimeout(
      () => document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth" }), SECTION_SCROLL_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [hash])
  const name = chat.lace?.name ?? "Lace"
  const subtitle = chat.lace?.startup_name ?? chat.lace?.website
  const select = (next: LaceTab) => navigate(`/lace/${laceId}/${next}`)
  const open = ({ tab: next, section }: FeedTarget) => {
    const scroll = () => section && document.getElementById(sectionId(section))?.scrollIntoView({ behavior: "smooth" })
    if (next === tab) return scroll()
    select(next)
    // The section mounts with the tab: scroll once it is there.
    window.setTimeout(scroll, SECTION_SCROLL_DELAY_MS)
  }
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
      <div className="relative flex min-h-0 flex-1">
        <LaceRail {...nav} className="absolute top-6 left-4 z-10 hidden md:flex" />
        <main className={tab === "chat" ? "flex min-h-0 min-w-0 flex-1 flex-col md:pl-20" : "min-h-0 min-w-0 flex-1 overflow-y-auto md:pl-20"}>
          {tab === "chat" && <LaceConversation chat={chat} name={name} onOpenMessaging={() => select("messaging")} />}
          {tab === "feed" && <LaceFeed laceId={laceId} name={name} chat={chat} activity={activity} onOpen={open} />}
          {tab === "messaging" && <LaceMessaging laceId={laceId} chat={chat} />}
        </main>
      </div>
      <LaceTabBar {...nav} className="md:hidden" />
      <LaceSettings laceId={laceId} name={name} facts={chat.facts} open={settingsOpen} onOpenChange={setSettingsOpen} />
    </div>
  )
}
