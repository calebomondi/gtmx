import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { localTimeZone, type BriefFrequency, type QuietHoursDto } from "@/lib/api"

import type { LaceSchedule } from "./use-lace-brief"

const FREQUENCIES: { id: BriefFrequency; label: string }[] = [
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "off", label: "Off" },
]
const HOURS = Array.from({ length: 24 }, (_, hour) => hour)
// What quiet hours start as when the founder turns them on.
const DEFAULT_QUIET: QuietHoursDto = { start: 22, end: 7 }

function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`
}

function HourSelect({ id, value, onChange }: { id: string; value: number; onChange: (hour: number) => void }) {
  return (
    <select id={id} value={value} onChange={(e) => onChange(Number(e.target.value))}
            className="h-8 w-fit rounded-md border border-input bg-transparent px-2 text-sm">
      {HOURS.map((hour) => <option key={hour} value={hour}>{hourLabel(hour)}</option>)}
    </select>
  )
}

export function Choice({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <Button size="sm" variant={active ? "default" : "outline"} aria-pressed={active} onClick={onClick}>
      {children}
    </Button>
  )
}

/** How often the Lace posts its brief, at what local hour, whether it is
 * emailed too, and the quiet hours in which nothing is emailed. */
export function LaceBrief({ schedule }: { schedule: LaceSchedule }) {
  const { settings, loading, error, update } = schedule
  if (loading) return <Skeleton className="h-16 w-full" />
  if (!settings) return <p className="text-sm text-destructive" role="alert">{error ?? "Couldn't load the brief settings."}</p>
  const here = localTimeZone()
  const quiet = settings.quiet_hours
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
            <Choice key={f.id} active={settings.brief_frequency === f.id}
                    onClick={() => void update({ brief_frequency: f.id })}>
              {f.label}
            </Choice>
          ))}
        </div>
      </section>
      {settings.brief_frequency !== "off" && (
        <>
          <section className="flex flex-col gap-2">
            <Label htmlFor="brief-hour">At</Label>
            <HourSelect id="brief-hour" value={settings.brief_hour} onChange={(hour) => void update({ brief_hour: hour })} />
            <p className="text-xs text-muted-foreground">
              {settings.timezone} time{settings.brief_frequency === "weekly" && ", on the day a week after the last brief"}.
            </p>
            {settings.timezone !== here && (
              <Button variant="outline" size="sm" className="w-fit" onClick={() => void update({ timezone: here })}>
                Use my timezone ({here})
              </Button>
            )}
          </section>
          <section className="flex flex-col gap-2">
            <Label>Email me the brief</Label>
            <div className="flex gap-2">
              <Choice active={settings.brief_email} onClick={() => void update({ brief_email: true })}>On</Choice>
              <Choice active={!settings.brief_email} onClick={() => void update({ brief_email: false })}>Off</Choice>
            </div>
            {!settings.email_available && (
              <p className="text-xs text-muted-foreground">Email isn't set up on this server yet; briefs stay in the chat.</p>
            )}
          </section>
          {settings.brief_email && (
            <section className="flex flex-col gap-2">
              <Label>Quiet hours</Label>
              <p className="text-xs text-muted-foreground">No emails in these hours; a brief written then arrives when they end.</p>
              {quiet ? (
                <div className="flex items-center gap-2 text-sm">
                  <Label htmlFor="quiet-start" className="sr-only">From</Label>
                  <HourSelect id="quiet-start" value={quiet.start}
                              onChange={(start) => void update({ quiet_hours: { ...quiet, start } })} />
                  <span>to</span>
                  <Label htmlFor="quiet-end" className="sr-only">Until</Label>
                  <HourSelect id="quiet-end" value={quiet.end}
                              onChange={(end) => void update({ quiet_hours: { ...quiet, end } })} />
                  <Button variant="ghost" size="sm" onClick={() => void update({ quiet_hours: null })}>Remove</Button>
                </div>
              ) : (
                <Button variant="outline" size="sm" className="w-fit"
                        onClick={() => void update({ quiet_hours: DEFAULT_QUIET })}>
                  Set quiet hours
                </Button>
              )}
            </section>
          )}
        </>
      )}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
  )
}
