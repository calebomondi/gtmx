import type { ReactNode } from "react"
import { ArrowRight, CheckCheck, FileText } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ActivityDto } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

import { ACTIVITY_ACTIONS, type FeedTarget } from "./lace-activity-actions"
import type { LaceActivity } from "./use-lace-activity"
import { useOpenedItems } from "./viewer-memory"

/** One thing a Lace did or found, with the button that acts on it. `lace`
 * names which Lace, in the feed across all of them. Once the founder has
 * followed it (`opened`) it quiets down and says so. */
export function ActivityRow({ item, fresh, opened = false, onOpen, lace }: {
  item: ActivityDto
  fresh: boolean
  opened?: boolean
  onOpen: (target: FeedTarget) => void
  lace?: ReactNode
}) {
  const action = ACTIVITY_ACTIONS[item.kind]
  return (
    <li className={cn("relative py-3 pl-3", opened && "opacity-70")}>
      {/* A thin rail on the left: the theme colour while new, red for a failure. */}
      <span aria-hidden className={cn("absolute top-3.5 bottom-3.5 left-0 w-0.5 rounded-full",
                                      item.kind === "job_failed" ? "bg-destructive" : fresh ? "bg-theme" : "bg-border")} />
      {lace}
      <p className={cn("text-sm break-words", opened ? "font-normal" : "font-medium")}>{item.title}</p>
      {item.summary && (
        <p className="mt-0.5 line-clamp-3 text-sm whitespace-pre-line text-muted-foreground">{item.summary}</p>
      )}
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          {formatRelativeTime(Date.parse(item.created_at))}
          {opened && <span className="flex items-center gap-1"><CheckCheck className="size-3.5" /> Opened</span>}
        </span>
        <Button size="sm" variant={opened ? "ghost" : "outline"} className="-my-1" onClick={() => onOpen(action.target)}>
          {action.label} <ArrowRight />
        </Button>
      </div>
    </li>
  )
}

const DAY_MS = 86_400_000

/** "Today", "Yesterday", "This week" or "Earlier", by the founder's clock. */
function dayGroup(iso: string, now = new Date()): string {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const at = Date.parse(iso)
  if (at >= startOfToday) return "Today"
  if (at >= startOfToday - DAY_MS) return "Yesterday"
  if (at >= startOfToday - 6 * DAY_MS) return "This week"
  return "Earlier"
}

/** Consecutive items under one day label; items arrive newest first. */
function byDay(items: ActivityDto[]): { label: string; items: ActivityDto[] }[] {
  const groups: { label: string; items: ActivityDto[] }[] = []
  for (const item of items) {
    const label = dayGroup(item.created_at)
    const last = groups[groups.length - 1]
    if (last?.label === label) last.items.push(item)
    else groups.push({ label, items: [item] })
  }
  return groups
}

/** What the Lace did or found, newest first and grouped by day, each with a
 * way to act on it; the ones already followed are marked. */
export function LaceActivityList({ activity, name, onOpen }: {
  activity: LaceActivity
  name: string
  onOpen: (target: FeedTarget) => void
}) {
  // One set across every Lace, so Home and each Feed agree.
  const [opened, markOpened] = useOpenedItems("activity")
  if (activity.loading) {
    return <div className="flex flex-col gap-3"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
  }
  if (activity.items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing yet. As {name} searches, drafts and hears back, it shows here.
      </p>
    )
  }
  return (
    <div className="flex flex-col">
      {byDay(activity.items).map((group) => (
        <section key={group.label} aria-label={group.label} className="mb-3">
          <h3 className="sticky top-12 z-[5] bg-background/90 py-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase backdrop-blur">
            {group.label}
          </h3>
          <ul className="divide-y rounded-xl border bg-card px-4">
            {group.items.map((item) => (
              <ActivityRow key={item.id} item={item} fresh={activity.isNew(item)} opened={opened.has(item.id)}
                           onOpen={(target) => {
                             markOpened(item.id)
                             onOpen(target)
                           }} />
            ))}
          </ul>
        </section>
      ))}
      {activity.hasMore && (
        <Button variant="ghost" size="sm" className="mt-2 self-center" onClick={() => void activity.loadMore()}>
          <FileText /> Older activity
        </Button>
      )}
      {activity.error && <p className="mt-2 text-sm text-destructive" role="alert">{activity.error}</p>}
    </div>
  )
}
