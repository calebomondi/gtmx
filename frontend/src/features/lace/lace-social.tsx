import { useState } from "react"
import { Radio } from "lucide-react"

import { PlatformIcon } from "@/components/platform-icon"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { InboxPlatform, SocialPlatform } from "@/lib/api"

import { AccountIcon } from "./lace-account-switcher"
import { SOCIAL_SECTIONS, type SocialSection } from "./lace-activity-actions"
import { LacePanelTabs, PanelIntro, type PanelTab } from "./lace-panel-tabs"
import { threadActions } from "./lace-thread-actions"
import { LaceThreads } from "./lace-threads"
import { LinkAccountCard } from "./link-account-card"
import { SocialEngagement } from "./social-engagement"
import { DM_PLATFORMS, messagesOn, postsOn, postsSummary, socialAccounts, type SocialAccount } from "./social-model"
import { SocialPosts } from "./social-posts"
import type { LaceApps } from "./use-lace-apps"
import type { LaceChat } from "./use-lace-chat"
import { useLaceSocial } from "./use-lace-social"
import { useSection } from "./use-lace-section"

/** What the Lace does on a platform, under its name. */
function howRead(account: SocialAccount, name: string): string {
  if (account.platform === "linkedin") return `${name} posts here on your approval; LinkedIn doesn't let it read posts or comments.`
  if (account.how === "handle") return `Read by your public handle @${account.handle}, nothing connected.`
  return `Connected. ${name} listens here once a day.`
}

/** The founder's own social accounts: per account, what people said (sorted
 * by the Lace into leads, questions, feedback and praise), the posts and how
 * they did, and direct messages with the answers the Lace drafted. */
export function LaceSocial({ laceId, name, chat, apps, discuss }: {
  laceId: string
  name: string
  chat: LaceChat
  apps: LaceApps
  discuss: (prompt: string) => void
}) {
  const social = useLaceSocial(laceId, true)
  const [section, setSection] = useSection<SocialSection>(SOCIAL_SECTIONS)
  const accounts = socialAccounts(apps.apps ?? [], social.heard ?? [])
  const [picked, setPicked] = useState<SocialPlatform | null>(null)
  const account = accounts.find((a) => a.platform === picked) ?? accounts[0]

  if (!apps.apps || social.posts === null || social.heard === null) {
    return social.error ? <p className="text-sm text-destructive" role="alert">{social.error}</p>
      : <Skeleton className="h-40 w-full rounded-2xl" />
  }
  if (!account) {
    return (
      <p className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        No social account yet. Connect Instagram, Facebook or LinkedIn, or save your X and TikTok handles, under
        Apps & accounts in {name}'s settings.
      </p>
    )
  }

  const heard = social.heard.filter((i) => i.platform === account.platform)
  const posts = postsOn(social.posts, account.platform)
  const summary = postsSummary(posts)
  const dms = DM_PLATFORMS.has(account.platform) ? messagesOn(chat.outreach, account.platform) : null
  const tabs: PanelTab<SocialSection>[] = [
    { value: "engagement", label: "Engagement", waiting: account.waiting,
      content: <SocialEngagement items={heard} name={name} social={social} discuss={discuss} /> },
    { value: "posts", label: "Posts", count: posts.length, content: <SocialPosts posts={posts} name={name} /> },
    ...(dms ? [{
      value: "messages" as const, label: "Messages", count: dms.length,
      content: (
        <>
          <PanelIntro>People who messaged your {account.label}, and the answers {name} drafted for you to send.</PanelIntro>
          <LaceThreads outreach={dms} folder="replies" drafting={chat.drafting} actions={threadActions(chat, name)}
                       empty={{ title: "No messages yet", body: `When someone messages your ${account.label}, it shows here.` }} />
        </>
      ),
    }] : []),
  ]
  const current = tabs.some((t) => t.value === section) ? section : "engagement"

  return (
    <LacePanelTabs label={`${name}'s Social`} tabs={tabs} value={current} onChange={setSection} header={
      <section aria-label="Social accounts" className="flex flex-col gap-3 rounded-2xl border bg-gradient-to-br from-theme/12 via-card to-card p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <h2 className="text-base font-medium">Social</h2>
          <Button size="sm" variant="outline" className="rounded-full"
                  onClick={() => discuss("Listen on my social accounts now and tell me what matters.")}>
            <Radio /> Listen now
          </Button>
        </div>
        <div className="flex items-center gap-2.5 overflow-x-auto px-1.5 py-1.5 [scrollbar-width:none]" role="group" aria-label="Accounts">
          {accounts.map((a) => (
            <AccountIcon key={a.platform} active={a.platform === account.platform} onClick={() => setPicked(a.platform)}
                         label={a.label} waiting={a.waiting} attention={a.needsLink}>
              <PlatformIcon platform={a.platform} className="size-5" />
            </AccountIcon>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{howRead(account, name)}</p>
        {account.needsLink && (
          <LinkAccountCard laceId={laceId} name={name} platform={account.platform as InboxPlatform}
                           onLinked={() => void apps.refresh()} />
        )}
        {summary && <p className="text-xs text-muted-foreground tabular-nums">{summary}</p>}
      </section>
    } />
  )
}
