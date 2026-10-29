import { useState } from "react"
import { ArrowRight } from "lucide-react"

import { Button } from "@/components/ui/button"

import { LaceActionsWaiting } from "./lace-apps"
import { FindReviewsCard } from "./find-reviews"
import { useFindReviews } from "./use-lace-finds"
import { FEED_SECTIONS, needsYou, type FeedSection, type FeedTarget, type NeedsYouItem } from "./lace-activity-actions"
import { LaceActivityList } from "./lace-activity"
import { accountItem, competitorItem, opportunityItem } from "./feed-review"
import { LaceAccounts } from "./lace-accounts"
import { LaceFunnel } from "./lace-funnel"
import { CompetitorMovesStepper } from "./lace-competitor-moves"
import { LaceCompetitors } from "./lace-competitors"
import { discussAccount, discussBrief, discussCompetitor, discussMove, discussOpportunity } from "./discuss"
import { LaceLatestBrief } from "./lace-latest-brief"
import { useLatestBrief } from "./use-latest-brief"
import { useLaceMoves } from "./use-lace-moves"
import { useSeenAt } from "./viewer-memory"
import { LaceOpportunities } from "./lace-opportunities"
import { LacePanelTabs, PanelIntro, type PanelTab } from "./lace-panel-tabs"
import { LaceReview } from "./lace-review"
import type { LaceActivity } from "./use-lace-activity"
import type { LaceOpportunities as Opportunities } from "./use-lace-opportunities"
import type { LaceApps } from "./use-lace-apps"
import type { LaceChat } from "./use-lace-chat"
import { useSection } from "./use-lace-section"

/** Where things stand: the pipeline, and what waits on the founder. */
function Pulse({ laceId, name, chat, activity, apps, needs, onOpen }: {
  laceId: string
  name: string
  chat: LaceChat
  activity: LaceActivity
  apps: LaceApps
  needs: NeedsYouItem[]
  onOpen: (target: FeedTarget) => void
}) {
  return (
    <section aria-label="Where things stand"
             className="flex flex-col gap-3 rounded-2xl border bg-gradient-to-br from-theme/12 via-card to-card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h2 className="text-base font-medium">Where things stand</h2>
        <p className="text-xs text-muted-foreground">
          {needs.length + apps.waiting > 0
            ? `${name} needs you for ${needs.length + apps.waiting} ${needs.length + apps.waiting === 1 ? "thing" : "things"}`
            : "Nothing waits on you"}
        </p>
      </div>
      <LaceFunnel laceId={laceId}
                  refreshKey={`${activity.items[0]?.id ?? ""}:${chat.accounts.length}:${chat.outreach.length}:${chat.waiting}`} />
      {needs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {needs.map((item) => (
            <Button key={item.label} size="sm" variant="outline" className="rounded-full border-theme/40 bg-background/70"
                    onClick={() => onOpen(item.target)}>
              <span aria-hidden className="size-1.5 rounded-full bg-theme" />
              {item.label} <ArrowRight />
            </Button>
          ))}
        </div>
      )}
      <LaceActionsWaiting chat={chat} apps={apps} />
    </section>
  )
}

/** What the Lace found and did, as sub-tabs under a short summary of where
 * things stand: its activity, the opportunities it turned up, the leads
 * worth reaching, and the competitors it tracks. Each holds what waits for
 * the founder's review above what was saved. */
export function LaceFeed({ laceId, name, chat, activity, opps, apps, onOpen, onDiscuss }: {
  laceId: string
  name: string
  chat: LaceChat
  activity: LaceActivity
  opps: Opportunities
  apps: LaceApps
  onOpen: (target: FeedTarget) => void
  /** Open the chat with a message about something here, ready to send. */
  onDiscuss: (prompt: string) => void
}) {
  const [section, setSection] = useSection<FeedSection>(FEED_SECTIONS)
  // Refetched as new activity arrives (a competitor check finished).
  const moves = useLaceMoves(laceId, activity.items[0]?.id ?? "")
  // A brief's Feed item changes when the brief is written, so key on its summary too.
  const { brief } = useLatestBrief(laceId, `${activity.items[0]?.id ?? ""}:${activity.items[0]?.summary ?? ""}`)
  const [movesSeenAt, markMovesSeen] = useSeenAt<"all">(`${laceId}.moves`)
  // The competitor the moves stepper shows; null for all of them.
  const [movesOf, setMovesOf] = useState<string | null>(null)
  const moveCounts = new Map<string, number>()
  for (const move of moves) moveCounts.set(move.competitor_id, (moveCounts.get(move.competitor_id) ?? 0) + 1)
  const showMoves = (competitorId: string) => {
    setMovesOf(competitorId)
    document.getElementById("competitor-moves")?.scrollIntoView({ behavior: "smooth", block: "start" })
  }
  // Teammates' pushes, loaded again as activity arrives (a push is a Feed item).
  const reviews = useFindReviews(laceId, activity.items[0]?.id ?? "")
  const needs = needsYou(chat.waiting, activity.items.filter((a) => a.kind === "job_failed" && activity.isNew(a)), {
    opportunities: opps.suggested.length, accounts: chat.suggestedAccounts.length,
    competitors: chat.suggestedCompetitors.length,
  }, chat.contacts.filter((c) => !c.approved_at).length, (reviews.items ?? []).filter((f) => f.can_review).length)

  const tabs: PanelTab<FeedSection>[] = [
    {
      value: "activity", label: "Activity", waiting: activity.unread,
      content: (
        <>
          <FindReviewsCard reviews={reviews} />
          <LaceLatestBrief brief={brief} name={name} onDiscuss={() => brief && onDiscuss(discussBrief(brief))} />
          <PanelIntro>What {name} did and found, newest first.</PanelIntro>
          <LaceActivityList activity={activity} name={name} onOpen={onOpen} />
        </>
      ),
    },
    {
      value: "opportunities", label: "Opportunities", count: opps.opportunities.length,
      waiting: opps.suggested.length, busy: chat.findingOpportunities,
      content: (
        <>
          <PanelIntro>Events to showcase at, tenders and buyers to sell to, partners, and grants and programmes you qualify for: sourced, and still open.</PanelIntro>
          <LaceReview items={opps.suggested.map(opportunityItem)} onSave={(id) => void opps.save(id)}
                      onDismiss={(id, why) => void opps.dismiss(id, why)} askWhy />
          <LaceOpportunities opps={opps} searching={chat.findingOpportunities} name={name}
                             onDiscuss={(o) => onDiscuss(discussOpportunity(o))} />
        </>
      ),
    },
    {
      value: "accounts", label: "Leads", count: chat.accounts.length,
      waiting: chat.suggestedAccounts.length, busy: chat.findingAccounts,
      content: (
        <>
          <PanelIntro>Companies that fit your ideal customer profile and have a reason to buy now, with the case for each.</PanelIntro>
          <LaceReview items={chat.suggestedAccounts.map(accountItem)} onSave={(id) => void chat.saveAccount(id)}
                      onDismiss={(id, why) => void chat.dismissAccount(id, why)} askWhy />
          <LaceAccounts accounts={chat.accounts} finding={chat.findingAccounts}
                        onDismiss={(id) => void chat.dismissAccount(id)} name={name}
                        onDiscuss={(a) => onDiscuss(discussAccount(a))} />
        </>
      ),
    },
    {
      value: "competitors", label: "Competitors", count: chat.competitors.length,
      waiting: chat.suggestedCompetitors.length, busy: chat.searching,
      content: (
        <>
          <PanelIntro>Companies your buyers could pay instead of you, profiled from sources and watched for moves.</PanelIntro>
          <LaceReview items={chat.suggestedCompetitors.map(competitorItem)} saveLabel="Track"
                      onSave={(id) => void chat.saveCompetitor(id)} onDismiss={(id) => void chat.dismissCompetitor(id)} />
          <CompetitorMovesStepper moves={moves} competitor={movesOf} onCompetitor={setMovesOf}
                                  seenAt={movesSeenAt("all")} onSeen={() => markMovesSeen("all")} name={name}
                                  onDiscuss={(m) => onDiscuss(discussMove(m.competitor_name, m.title, m.detected_at, m.sources))} />
          <LaceCompetitors competitors={chat.competitors} searching={chat.searching}
                           onDismiss={(id) => void chat.dismissCompetitor(id)} moveCounts={moveCounts}
                           onShowMoves={showMoves} name={name} onDiscuss={(c) => onDiscuss(discussCompetitor(c))} />
        </>
      ),
    },
  ]

  return (
    <LacePanelTabs label={`${name}'s Feed`} tabs={tabs} value={section} onChange={setSection}
                   header={<Pulse laceId={laceId} name={name} chat={chat} activity={activity} apps={apps} needs={needs} onOpen={onOpen} />} />
  )
}
