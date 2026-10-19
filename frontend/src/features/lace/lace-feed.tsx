import { LaceAccounts } from "./lace-accounts"
import { LaceCompetitors } from "./lace-competitors"
import { LaceOpportunities } from "./lace-opportunities"
import { LaceSection } from "./lace-section"
import type { LaceChat } from "./use-lace-chat"

/** What the Lace has found: opportunities, target accounts and competitors.
 * The activity feed (docs/lace-ui-plan.md, PR E) joins these at the top. */
export function LaceFeed({ laceId, chat }: { laceId: string; chat: LaceChat }) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      <LaceSection title="Opportunities" busy={chat.findingOpportunities}
                   description="Events to showcase at, tenders and buyers to sell to, and partners: sourced, and still open.">
        <LaceOpportunities laceId={laceId} searching={chat.findingOpportunities} />
      </LaceSection>
      <LaceSection title={`Target accounts (${chat.accounts.length})`} busy={chat.findingAccounts}
                   description="Who matches your ideal customer and has a reason to buy now, with the case for each.">
        <LaceAccounts accounts={chat.accounts} finding={chat.findingAccounts}
                      onDismiss={(id) => void chat.dismissAccount(id)} />
      </LaceSection>
      <LaceSection title={`Competitors (${chat.competitors.length})`} busy={chat.searching}
                   description="Companies your buyers could pay instead of you, each checked and profiled from sources.">
        <LaceCompetitors competitors={chat.competitors} searching={chat.searching}
                         onDismiss={(id) => void chat.dismissCompetitor(id)} />
      </LaceSection>
    </div>
  )
}
