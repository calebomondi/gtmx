import { ArrowRight } from "lucide-react"

import { Button } from "@/components/ui/button"

import { needsYou, sectionId, type FeedTarget } from "./lace-activity-actions"
import { LaceActivityList } from "./lace-activity"
import { LaceAccounts } from "./lace-accounts"
import { LaceFunnel } from "./lace-funnel"
import { LaceCompetitors } from "./lace-competitors"
import { LaceOpportunities } from "./lace-opportunities"
import { LaceSection } from "./lace-section"
import type { LaceActivity } from "./use-lace-activity"
import type { LaceChat } from "./use-lace-chat"

/** The Lace's notification centre: what waits on the founder, what it did
 * or found, then the opportunities, target accounts and competitors on file. */
export function LaceFeed({ laceId, name, chat, activity, onOpen }: {
  laceId: string
  name: string
  chat: LaceChat
  activity: LaceActivity
  onOpen: (target: FeedTarget) => void
}) {
  const needs = needsYou(chat.waiting, activity.items.filter((a) => a.kind === "job_failed" && activity.isNew(a)))
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      {needs.length > 0 && (
        <section aria-label="Needs you" className="flex flex-wrap items-center gap-2 rounded-xl border border-theme/40 bg-theme/10 p-3">
          <span className="text-sm font-medium">Needs you</span>
          {needs.map((item) => (
            <Button key={item.label} size="sm" variant="outline" onClick={() => onOpen(item.target)}>
              {item.label} <ArrowRight />
            </Button>
          ))}
        </section>
      )}
      <LaceFunnel laceId={laceId} refreshKey={`${activity.items[0]?.id ?? ""}:${chat.outreach.length}:${chat.waiting}`} />
      <LaceSection title="Activity" description={`What ${name} did and found, newest first.`}>
        <LaceActivityList activity={activity} name={name} onOpen={onOpen} />
      </LaceSection>
      <LaceSection id={sectionId("opportunities")} title="Opportunities" busy={chat.findingOpportunities}
                   description="Events to showcase at, tenders and buyers to sell to, and partners: sourced, and still open.">
        <LaceOpportunities laceId={laceId} searching={chat.findingOpportunities} />
      </LaceSection>
      <LaceSection id={sectionId("accounts")} title={`Target accounts (${chat.accounts.length})`} busy={chat.findingAccounts}
                   description="Who matches your ideal customer and has a reason to buy now, with the case for each.">
        <LaceAccounts accounts={chat.accounts} finding={chat.findingAccounts}
                      onDismiss={(id) => void chat.dismissAccount(id)} />
      </LaceSection>
      <LaceSection id={sectionId("competitors")} title={`Competitors (${chat.competitors.length})`} busy={chat.searching}
                   description="Companies your buyers could pay instead of you, each checked and profiled from sources.">
        <LaceCompetitors competitors={chat.competitors} searching={chat.searching}
                         onDismiss={(id) => void chat.dismissCompetitor(id)} />
      </LaceSection>
    </div>
  )
}
