import {
  AlertTriangle, Building2, FileText, Inbox, Newspaper, PenLine, Sparkles, Swords, Users,
  type LucideIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ActivityKind } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"
import { cn } from "@/lib/utils"

import { ACTIVITY_ACTIONS, type FeedTarget } from "./lace-activity-actions"
import type { LaceActivity } from "./use-lace-activity"

const ICONS: Record<ActivityKind, LucideIcon> = {
  brief: Newspaper,
  competitors_found: Swords,
  competitor_moves: Swords,
  accounts_found: Building2,
  contacts_found: Users,
  drafts_ready: PenLine,
  reply_received: Inbox,
  opportunities_found: Sparkles,
  job_failed: AlertTriangle,
}

/** What the Lace did or found, newest first, each with a way to act on it. */
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
      <ul className="divide-y">
        {activity.items.map((item) => {
          const Icon = ICONS[item.kind]
          const action = ACTIVITY_ACTIONS[item.kind]
          const fresh = activity.isNew(item)
          return (
            <li key={item.id} className="flex items-start gap-3 py-3">
              <span className={cn("mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-muted",
                                  item.kind === "job_failed" ? "text-destructive" : "text-theme")}>
                <Icon className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex items-baseline gap-2 text-sm font-medium">
                  {fresh && <span className="size-2 shrink-0 translate-y-[-1px] rounded-full bg-theme" aria-label="New" />}
                  <span className="min-w-0 break-words">{item.title}</span>
                </p>
                {item.summary && (
                  <p className="mt-0.5 line-clamp-3 text-sm whitespace-pre-line text-muted-foreground">{item.summary}</p>
                )}
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">{formatRelativeTime(Date.parse(item.created_at))}</span>
                  <Button size="sm" variant="ghost" className="-my-1" onClick={() => onOpen(action.target)}>
                    {action.label}
                  </Button>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
      {activity.hasMore && (
        <Button variant="ghost" size="sm" className="mt-2 self-center" onClick={() => void activity.loadMore()}>
          <FileText /> Older activity
        </Button>
      )}
      {activity.error && <p className="mt-2 text-sm text-destructive" role="alert">{activity.error}</p>}
    </div>
  )
}
