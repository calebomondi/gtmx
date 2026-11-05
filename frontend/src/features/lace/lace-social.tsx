import { useEffect } from "react"
import { useLocation, useNavigate, useSearchParams } from "react-router-dom"
import { Radio } from "lucide-react"

import { PlatformIcon } from "@/components/platform-icon"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { InboxPlatform } from "@/lib/api"

import { AccountIcon } from "./lace-account-switcher"
import { SOCIAL_SECTIONS, type SocialSection } from "./lace-activity-actions"
import { LacePanelTabs, PanelIntro, type PanelTab } from "./lace-panel-tabs"
import { threadActions } from "./lace-thread-actions"
import { LaceThreads } from "./lace-threads"
import { LinkAccountCard } from "./link-account-card"
import { isUnread } from "./outreach-threads"
import { SocialEngagement } from "./social-engagement"
import {
  DM_PLATFORMS, listensOn, messagesOn, postsOn, postsSummary, socialAccounts, type SocialAccount,
  type SocialAccountPlatform,
} from "./social-model"
import { SocialPosts } from "./social-posts"
import type { LaceApps } from "./use-lace-apps"
import type { LaceChat } from "./use-lace-chat"
import { useLaceSocial } from "./use-lace-social"
import { useSection } from "./use-lace-section"
import { useSeenAt } from "./viewer-memory"

/** What the Lace does on a platform, under its name. */
function howRead(account: SocialAccount, name: string): string {
  if (account.platform === "telegram") return `Connected. People who write to your bot show under Messages, with the answers ${name} drafts.`
  if (account.platform === "linkedin") return `${name} posts here on your approval; LinkedIn doesn't let it read posts or comments.`
  if (account.how === "handle") return `Read by your public handle @${account.handle}, nothing connected.`
  return `Connected. ${name} listens here once a day.`
}

/** The founder's own social accounts: per account, what people said (sorted
 * by the Lace into leads, questions, feedback and praise), the posts and how
 * they did, and direct messages with the answers the Lace drafted. The
 * account open rides in the URL (?account=), so the Feed can link to it. */
export function LaceSocial({ laceId, name, chat, apps, discuss }: {
  laceId: string
  name: string
  chat: LaceChat
  apps: LaceApps
  discuss: (prompt: string) => void
}) {
  const social = useLaceSocial(laceId, true)
  const [section, setSection] = useSection<SocialSection>(SOCIAL_SECTIONS)
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { hash } = useLocation()
  const [seenAt, markSeen] = useSeenAt<SocialAccountPlatform>(`${laceId}.social`)
  const accounts = socialAccounts(apps.apps ?? [], social.heard ?? [], chat.outreach, seenAt)
  const requested = accounts.find((a) => a.platform === params.get("account"))
  // Sent to Messages with no account named: the first with a message to read.
  const unreadFirst = section === "messages"
    ? accounts.find((a) => messagesOn(chat.outreach, a.platform).some(isUnread)) : undefined
  const account = requested ?? unreadFirst ?? accounts[0]
  // Another account keeps the tab open (the hash), where it has one.
  const pick = (platform: SocialAccountPlatform) => {
    const next = new URLSearchParams(params)
    next.set("account", platform)
    navigate({ search: next.toString(), hash }, { replace: true })
  }
  const shown = account?.platform
  useEffect(() => {
    if (shown) markSeen(shown)
  }, [shown, markSeen])

  if (!apps.apps || social.posts === null || social.heard === null) {
    return social.error ? <p className="text-sm text-destructive" role="alert">{social.error}</p>
      : <Skeleton className="h-40 w-full rounded-2xl" />
  }
  if (!account) {
    return (
      <p className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        No social account yet. Connect Instagram, Facebook, Telegram or LinkedIn, or save your X and TikTok handles,
        under Apps & accounts in {name}'s settings.
      </p>
    )
  }

  const platform = account.platform
  const posts = listensOn(platform) ? postsOn(social.posts, platform) : []
  const summary = postsSummary(posts)
  const dms = DM_PLATFORMS.has(platform) ? messagesOn(chat.outreach, platform) : null
  const tabs: PanelTab<SocialSection>[] = [
    ...(listensOn(platform) ? [
      { value: "engagement" as const, label: "Engagement",
        content: <SocialEngagement items={social.heard.filter((i) => i.platform === platform)} name={name}
                                   social={social} discuss={discuss} /> },
      { value: "posts" as const, label: "Posts", count: posts.length, content: <SocialPosts posts={posts} name={name} /> },
    ] : []),
    ...(dms ? [{
      value: "messages" as const, label: "Messages", count: dms.length, waiting: dms.filter(isUnread).length,
      content: (
        <>
          <PanelIntro>People who messaged your {account.label}, and the answers {name} drafted for you to send.</PanelIntro>
          <LaceThreads outreach={dms} folder="replies" drafting={chat.drafting} actions={threadActions(chat, name)}
                       empty={{ title: "No messages yet", body: `When someone messages your ${account.label}, it shows here.` }} />
        </>
      ),
    }] : []),
  ]
  const current = tabs.some((t) => t.value === section) ? section : tabs[0].value

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
            <AccountIcon key={a.platform} active={a.platform === platform} onClick={() => pick(a.platform)}
                         label={a.label} waiting={a.platform === platform ? 0 : a.waiting} attention={a.needsLink}>
              <PlatformIcon platform={a.platform} className="size-5" />
            </AccountIcon>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{howRead(account, name)}</p>
        {account.needsLink && (
          <LinkAccountCard laceId={laceId} name={name} platform={platform as InboxPlatform}
                           onLinked={() => void apps.refresh()} />
        )}
        {summary && <p className="text-xs text-muted-foreground tabular-nums">{summary}</p>}
      </section>
    } />
  )
}
