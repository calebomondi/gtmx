import type { HeardKind, LaceAppDto, LaceOutreachDto, SocialItemDto, SocialPlatform, SocialPostDto } from "@/lib/api"
import { PLATFORM_LABEL } from "@/lib/platforms"

/** The founder's accounts the Social view shows, in this order. */
const SOCIAL_ORDER: SocialPlatform[] = ["instagram", "facebook", "x", "tiktok", "linkedin"]
/** Platforms whose direct messages the Lace reads and answers. */
export const DM_PLATFORMS: ReadonlySet<SocialPlatform> = new Set(["instagram", "facebook"])

export interface SocialAccount {
  platform: SocialPlatform
  label: string
  /** connected: through the app; handle: read by the founder's public handle, nothing connected. */
  how: "connected" | "handle"
  handle: string | null
  /** Connected, but the Page or business account isn't linked to the Lace yet. */
  needsLink: boolean
  /** Leads and questions waiting on the founder. */
  waiting: number
}

/** The founder's social accounts a Lace reads: connected ones, and those read by a saved handle. */
export function socialAccounts(apps: LaceAppDto[], heard: SocialItemDto[]): SocialAccount[] {
  return SOCIAL_ORDER.flatMap((platform) => {
    const app = apps.find((a) => a.platform === platform)
    const handle = app?.settings.handle ?? null
    if (!app || (!app.connected && !handle)) return []
    return [{
      platform, label: PLATFORM_LABEL[platform], how: app.connected ? "connected" : "handle", handle,
      needsLink: app.needs_link,
      waiting: heard.filter((i) => i.platform === platform && i.status === "new" && needsReply(i.verdict)).length,
    }]
  })
}

function needsReply(kind: HeardKind): boolean {
  return kind === "lead" || kind === "question"
}

/** How what was heard is shown, most pressing first. */
export const HEARD_SECTIONS: { kind: HeardKind; title: string }[] = [
  { kind: "lead", title: "Leads worth engaging" },
  { kind: "question", title: "Questions waiting for an answer" },
  { kind: "feedback", title: "Feedback" },
  { kind: "praise", title: "Praise" },
]

/** What the founder asks their Lace to do with something heard, written into the chat for them to send. */
export function askAbout(item: SocialItemDto): string {
  const who = `@${item.author ?? "someone"} on ${PLATFORM_LABEL[item.platform]}`
  const said = `"${item.text}"${item.url ? ` (${item.url})` : ""}`
  switch (item.verdict) {
    case "lead":
      return `${who} looks like a lead: ${said}. Find out who they are and an email to reach them, and suggest how to engage.`
    case "question":
      return `Draft a reply to ${who}'s question: ${said}`
    case "feedback":
      return `What should we do about this feedback from ${who}: ${said}?`
    default:
      return `Draft a short thank-you reply to ${who}: ${said}`
  }
}

export function postsOn(posts: SocialPostDto[], platform: SocialPlatform): SocialPostDto[] {
  return posts.filter((p) => p.platform === platform)
}

function counted(n: number, one: string, many: string): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`
}

/** "Last 3 posts: 1,200 views · 41 likes · 6 comments", leaving out what the
 * platform doesn't count (Instagram has no views); null with no posts. */
export function postsSummary(posts: SocialPostDto[]): string | null {
  if (posts.length === 0) return null
  const metrics: [keyof SocialPostDto, string, string][] = [["views", "view", "views"], ["likes", "like", "likes"],
                                                           ["comments", "comment", "comments"]]
  const parts = metrics.flatMap(([key, one, many]) => {
    const known = posts.map((p) => p[key]).filter((v): v is number => typeof v === "number")
    return known.length ? [counted(known.reduce((a, b) => a + b, 0), one, many)] : []
  })
  const which = posts.length === 1 ? "Last post" : `Last ${posts.length} posts`
  return parts.length ? `${which}: ${parts.join(" · ")}` : null
}

/** Direct messages on a platform: what the Messages tab threads. */
export function messagesOn(outreach: LaceOutreachDto[], platform: SocialPlatform): LaceOutreachDto[] {
  return outreach.filter((m) => m.channel === platform)
}
