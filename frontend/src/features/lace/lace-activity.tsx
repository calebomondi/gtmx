import type { ReactNode } from "react"
import { ArrowRight, CheckCheck, FileText } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ActivityDto } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"

import { byDay, dayLabel, timeOfDay } from "./activity-days"
import { activityAction, type FeedTarget } from "./lace-activity-actions"
import { PersonAvatar } from "./person-avatar"
import type { LaceActivity } from "./use-lace-activity"
import { useOpenedItems } from "./viewer-memory"

/** One step of a day: the time, a node on the rail (filled while new, hollow
 * once followed, red for a failure), and what happened with its action. */
function Step<T extends ActivityDto>({ item, fresh, opened, last, onOpen, tag }: {
  item: T
  fresh: boolean
  opened: boolean
  last: boolean
  onOpen: (target: FeedTarget) => void
  tag?: ReactNode
}) {
  const { user } = useAuth()
  const action = activityAction(item.kind)
  const failed = item.kind === "job_failed"
  const by = item.actor && (item.actor.id === user?.id ? "You" : (item.actor.name ?? "Someone on your team"))
  return (
    <li className="grid grid-cols-[4.25rem_1.25rem_1fr] gap-x-2">
      <time dateTime={item.created_at} className="pt-0.5 text-right text-xs whitespace-nowrap text-muted-foreground tabular-nums">
        {timeOfDay(item.created_at)}
      </time>
      <div className="relative flex justify-center">
        <span aria-hidden className={cn("relative z-[1] mt-1 size-3 rounded-full border-2",
                                        failed ? "border-destructive bg-destructive"
                                          : opened ? "border-muted-foreground/50 bg-background"
                                            : fresh ? "border-theme bg-theme shadow-[0_0_10px] shadow-theme/60"
                                              : "border-theme bg-background")} />
        {!last && <span aria-hidden className="absolute top-4 bottom-0 w-px bg-border" />}
      </div>
      <div className={cn("min-w-0 pb-5", opened && "opacity-70")}>
        {tag}
        <p className={cn("text-sm break-words", opened ? "font-normal" : "font-medium")}>{item.title}</p>
        {item.summary && (
          <p className="mt-0.5 line-clamp-3 text-sm whitespace-pre-line text-muted-foreground">{item.summary}</p>
        )}
        {item.actor && (
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            <PersonAvatar name={item.actor.name} email={null} avatarUrl={item.actor.avatar_url} size="sm" className="size-4" />
            {by}
          </p>
        )}
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <Button size="xs" variant={opened ? "ghost" : "outline"} onClick={() => onOpen(action.target)}>
            {action.label} <ArrowRight />
          </Button>
          {opened && <span className="flex items-center gap-1 text-xs text-muted-foreground"><CheckCheck className="size-3.5" /> Opened</span>}
        </div>
      </div>
    </li>
  )
}

/** Activity as one stepper per day: a card for each day, its updates as
 * steps on a rail, newest first. Followed items are remembered (across
 * every Lace, so Home and each Feed agree) and quiet down. `tag` labels a
 * step, e.g. with its Lace on Home. */
export function ActivityStepper<T extends ActivityDto>({ items, isFresh, onOpen, tag }: {
  items: T[]
  isFresh: (item: T) => boolean
  onOpen: (item: T, target: FeedTarget) => void
  tag?: (item: T) => ReactNode
}) {
  const [opened, markOpened] = useOpenedItems("activity")
  return (
    <div className="flex flex-col gap-4">
      {byDay(items, (item) => item.created_at).map((group) => (
        <section key={group.day} aria-label={dayLabel(group.day)} className="rounded-xl border bg-card">
          <h3 className="flex items-baseline justify-between gap-2 border-b px-4 py-2.5">
            <span className="text-sm font-medium">{dayLabel(group.day)}</span>
            <span className="text-xs text-muted-foreground">
              {group.items.length} {group.items.length === 1 ? "update" : "updates"}
            </span>
          </h3>
          <ol className="px-2 pt-4 pr-4">
            {group.items.map((item, i) => (
              <Step key={item.id} item={item} fresh={isFresh(item)} opened={opened.has(item.id)}
                    last={i === group.items.length - 1} tag={tag?.(item)}
                    onOpen={(target) => {
                      markOpened(item.id)
                      onOpen(item, target)
                    }} />
            ))}
          </ol>
        </section>
      ))}
    </div>
  )
}

/** What the Lace did or found, as a stepper per day, each with a way to act
 * on it. */
export function LaceActivityList({ activity, name, onOpen }: {
  activity: LaceActivity
  name: string
  onOpen: (target: FeedTarget) => void
}) {
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
      <ActivityStepper items={activity.items} isFresh={activity.isNew} onOpen={(_, target) => onOpen(target)} />
      {activity.hasMore && (
        <Button variant="ghost" size="sm" className="mt-2 self-center" onClick={() => void activity.loadMore()}>
          <FileText /> Older activity
        </Button>
      )}
      {activity.error && <p className="mt-2 text-sm text-destructive" role="alert">{activity.error}</p>}
    </div>
  )
}
