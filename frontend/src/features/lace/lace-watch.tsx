import { Skeleton } from "@/components/ui/skeleton"
import type { WatchEvery } from "@/lib/api"

import { Choice } from "./lace-brief"
import type { LaceSchedule } from "./use-lace-brief"

const EVERY: { hours: WatchEvery; label: string }[] = [
  { hours: 6, label: "6 hours" },
  { hours: 12, label: "12 hours" },
  { hours: 24, label: "Daily" },
  { hours: 168, label: "Weekly" },
]

/** How often the Lace looks, on its own, for new opportunities and for what
 * competitors changed; and how often replies are checked (set by the server). */
export function LaceWatch({ name, schedule }: { name: string; schedule: LaceSchedule }) {
  const { settings, loading, update } = schedule
  if (loading) return <Skeleton className="h-16 w-full" />
  if (!settings) return null  // the Brief section below says why
  const replies = settings.reply_check_minutes
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted-foreground">
        How often {name} looks for new opportunities and checks what competitors changed.
      </p>
      <div className="flex flex-wrap gap-2">
        {EVERY.map((option) => (
          <Choice key={option.hours} active={settings.watch_every_h === option.hours}
                  onClick={() => void update({ watch_every_h: option.hours })}>
            {option.label}
          </Choice>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {replies > 0
          ? `Replies to messages you sent are checked every ${replies} minutes.`
          : "Replies to messages you sent aren't checked on this server."}
      </p>
    </div>
  )
}
