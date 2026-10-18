import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { localTimeZone, type BriefFrequency } from "@/lib/api"

import { useLaceBrief } from "./use-lace-brief"

const FREQUENCIES: { id: BriefFrequency; label: string }[] = [
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "off", label: "Off" },
]
const HOURS = Array.from({ length: 24 }, (_, hour) => hour)

function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

/** How often the Lace posts its brief in the chat, and at what local hour. */
export function LaceBrief({ laceId }: { laceId: string }) {
  const { settings, loading, error, update } = useLaceBrief(laceId)
  if (loading) return <Skeleton className="h-16 w-full" />
  if (!settings) return <p className="text-sm text-destructive" role="alert">{error ?? "Couldn't load the brief settings."}</p>
  const here = localTimeZone()
  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-muted-foreground">
        Your Lace sums up what changed: competitor moves, new accounts, replies, drafts waiting for you and
        opportunities closing soon. Days with nothing new get no brief.
      </p>
      <section className="flex flex-col gap-2">
        <Label>How often</Label>
        <div className="flex gap-2">
          {FREQUENCIES.map((f) => (
            <Button key={f.id} size="sm" variant={settings.brief_frequency === f.id ? "default" : "outline"}
                    aria-pressed={settings.brief_frequency === f.id}
                    onClick={() => void update({ brief_frequency: f.id })}>
              {f.label}
            </Button>
          ))}
        </div>
      </section>
      {settings.brief_frequency !== "off" && (
        <section className="flex flex-col gap-2">
          <Label htmlFor="brief-hour">At</Label>
          <select id="brief-hour" value={settings.brief_hour}
                  onChange={(e) => void update({ brief_hour: Number(e.target.value) })}
                  className="h-8 w-fit rounded-md border border-input bg-transparent px-2 text-sm">
            {HOURS.map((hour) => <option key={hour} value={hour}>{hourLabel(hour)}</option>)}
          </select>
          <p className="text-xs text-muted-foreground">
            {settings.timezone} time{settings.brief_frequency === "weekly" && ", on the day a week after the last brief"}.
          </p>
          {settings.timezone !== here && (
            <Button variant="outline" size="sm" className="w-fit" onClick={() => void update({ timezone: here })}>
              Use my timezone ({here})
            </Button>
          )}
        </section>
      )}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
  )
}
