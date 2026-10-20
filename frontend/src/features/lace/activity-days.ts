import type { ActivityDto } from "@/lib/api"

const DAY_MS = 86_400_000

function startOfDay(at: Date): number {
  return new Date(at.getFullYear(), at.getMonth(), at.getDate()).getTime()
}

/** "Today", "Yesterday", then "Mon 19 Oct" (with the year when not this one). */
export function dayLabel(dayStart: number, now = new Date()): string {
  const today = startOfDay(now)
  if (dayStart === today) return "Today"
  if (dayStart === today - DAY_MS) return "Yesterday"
  const day = new Date(dayStart)
  return day.toLocaleDateString(undefined, {
    weekday: "short", day: "numeric", month: "short",
    ...(day.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
  })
}

/** "09:12" in the founder's clock. */
export function timeOfDay(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
}

/** Items (newest first) in one group per calendar day, newest day first. */
export function byDay<T extends ActivityDto>(items: T[]): { day: number; items: T[] }[] {
  const days: { day: number; items: T[] }[] = []
  for (const item of items) {
    const day = startOfDay(new Date(item.created_at))
    const last = days[days.length - 1]
    if (last?.day === day) last.items.push(item)
    else days.push({ day, items: [item] })
  }
  return days
}
