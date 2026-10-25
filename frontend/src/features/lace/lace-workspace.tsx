import { useEffect, useState } from "react"
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom"
import { RotateCcw, Settings2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ensureLacesLoaded, useLaces } from "@/lib/laces-store"

import { JOB_INFO } from "./background-jobs"
import type { DiscussState } from "./discuss"
import { sectionHash, type FeedTarget } from "./lace-activity-actions"
import { LaceBackgroundWork } from "./lace-background-work"
import { LaceConversation } from "./lace-conversation"
import { foundSections, type FoundSection } from "./found-model"
import { useSeenAt } from "./viewer-memory"
import { LaceFeed } from "./lace-feed"
import { LaceFindsDock } from "./lace-finds-dock"
import { LaceInviteGate } from "./lace-invite-gate"
import { LacePeopleButton } from "./lace-people"
import { LaceMessaging } from "./lace-messaging"
import { LaceRail, LaceTabBar } from "./lace-rail"
import { useLaceApps } from "./use-lace-apps"
import { useLacePeople } from "./use-lace-people"
import { QuickAskChips } from "./lace-quick-asks"
import { quickAsks } from "./quick-asks"
import { chatMascot, LACE_TABS, type LaceTab } from "./lace-tabs"
import { LaceSettings } from "./lace-settings"
import { LaceStatusBanner } from "./lace-status-banner"
import { useLaceActivity } from "./use-lace-activity"
import { useLaceChat } from "./use-lace-chat"
import { useLaceOpportunities } from "./use-lace-opportunities"

function isTab(value: string | undefined): value is LaceTab {
  return LACE_TABS.includes(value as LaceTab)
}

/** One Lace: Feed, the chat and Messaging, reached from three round buttons.
 * It opens on Feed. Keyed on the Lace id, so moving to another Lace starts
 * fresh. */
export default function LaceWorkspacePage() {
  // The route only renders this page with a lace_id.
  const { lace_id: laceId = "", tab } = useParams()
  const { invites } = useLaces()
  useEffect(ensureLacesLoaded, [])
  // Invited and not yet answered: the invite, and nothing of the Lace.
  const invite = invites.find((i) => i.lace_id === laceId)
  if (invite) return <LaceInviteGate invite={invite} />
  if (tab !== undefined && !isTab(tab)) return <Navigate to={`/lace/${laceId}`} replace />
  return <LaceWorkspace key={laceId} laceId={laceId} tab={tab ?? "feed"} />
}

function LaceWorkspace({ laceId, tab }: { laceId: string; tab: LaceTab }) {
  const navigate = useNavigate()
  // One load of the Lace serves all three tabs, so the chat keeps following
  // its run while the founder looks at the Feed.
  const chat = useLaceChat(laceId)
  const activity = useLaceActivity(laceId, tab === "feed")

  // Refetched as new activity arrives (an opportunity search finished).
  const opps = useLaceOpportunities(laceId, activity.items[0]?.id ?? "")
  // Back from connecting an app from the settings: open them again there.
  // Open on coming back from connecting an app, or when sent here to change a setting (?settings).
  const [settingsOpen, setSettingsOpen] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    return params.has("connected") || params.has("settings")
  })
  // The apps load with the settings and the chat, whose quick asks come from them.
  const apps = useLaceApps(laceId, settingsOpen || tab === "chat")
  const asks = quickAsks(apps.apps)
  // Shared by the header's faces and the chat, which shows who sent what in a team.
  const people = useLacePeople(laceId)
  const team = (people.people ?? []).filter((p) => p.status === "active").length > 1
  const [seenAt, markSeen] = useSeenAt<FoundSection["key"]>(laceId)
  const name = chat.lace?.name ?? "Lace"
  const subtitle = chat.lace?.startup_name ?? chat.lace?.website
  const select = (next: LaceTab) => navigate(`/lace/${laceId}/${next}`)
  // The sub-tab rides in the hash, which Feed and Messaging read.
  const [peopleOpen, setPeopleOpen] = useState(false)
  const open = ({ tab: next, section, people: toPeople }: FeedTarget) => {
    navigate(`/lace/${laceId}/${next}${section ? sectionHash(section) : ""}`)
    if (toPeople) setPeopleOpen(true)
  }
  // "Discuss with…": into the chat with the topic waiting in the input.
  const discuss = (prompt: string) =>
    navigate(`/lace/${laceId}/chat`, { state: { prefill: prompt } satisfies DiscussState })
  const location = useLocation()
  const discussing = (location.state as DiscussState | null)?.prefill
  const prefill = discussing ? { key: location.key, text: discussing } : undefined
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
  const found = foundSections(chat, opps, open)
  // Kinds of find a background job is filling now: their chips spin.
  const searching = new Set(chat.jobs.flatMap((job) => JOB_INFO[job.kind]?.fills ?? []))
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-base font-medium">{name}</h1>
          {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {chat.lace && <LacePeopleButton name={name} me={chat.lace.role} people={people} open={peopleOpen}
                                          onOpenChange={setPeopleOpen} />}
          <Button variant="outline" size="icon-sm" onClick={() => setSettingsOpen(true)} disabled={chat.loading}
                  aria-label={`${name}'s settings`} title="Settings">
            <Settings2 />
          </Button>
        </div>
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
          {tab === "chat" && (
            <LaceConversation chat={chat} name={name} onOpenMessaging={() => select("messaging")} prefill={prefill} team={team}
                              starters={<QuickAskChips asks={asks} onAsk={(text) => void chat.send(text)} disabled={chat.working} />}
                              dock={
              <>
                <LaceBackgroundWork name={name} jobs={chat.jobs} />
                <LaceFindsDock name={name} sections={found} seenAt={seenAt} onSeen={markSeen} busy={chat.working} searching={searching}
                               onAsk={(prompt) => void chat.send(prompt)} />
              </>
            } />
          )}
          {tab === "feed" && (
            <LaceFeed laceId={laceId} name={name} chat={chat} activity={activity} opps={opps} apps={apps} onOpen={open}
                      onDiscuss={discuss} />
          )}
          {tab === "messaging" && <LaceMessaging laceId={laceId} name={name} chat={chat} />}
        </main>
      </div>
      <LaceTabBar {...nav} className="md:hidden" />
      <LaceSettings laceId={laceId} name={name} status={chat.lace?.status ?? "active"} role={chat.lace?.role ?? "member"} facts={chat.facts}
                    apps={apps} open={settingsOpen} onOpenChange={setSettingsOpen} onChanged={() => void chat.reload()} />
    </div>
  )
}
