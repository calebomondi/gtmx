import type { LaceAccountDto, LeadTemperature } from "@/lib/api"

/** The order leads are worked in, and the filter chips' order. */
export const TEMPERATURES: LeadTemperature[] = ["hot", "warm", "cold", "customer"]

export const TEMPERATURE_LABEL: Record<LeadTemperature, string> = {
  hot: "Hot", warm: "Warm", cold: "Cold", customer: "Customer",
}

export type TemperatureFilter = LeadTemperature | "all"

/** How many leads each chip would show, "all" included. */
export function temperatureCounts(accounts: LaceAccountDto[]): Record<TemperatureFilter, number> {
  const counts: Record<TemperatureFilter, number> = { all: accounts.length, hot: 0, warm: 0, cold: 0, customer: 0 }
  for (const a of accounts) counts[a.temperature] += 1
  return counts
}

/** The leads a chip shows, hottest first (the server's order is kept within each temperature). */
export function byTemperature(accounts: LaceAccountDto[], filter: TemperatureFilter): LaceAccountDto[] {
  const shown = filter === "all" ? accounts : accounts.filter((a) => a.temperature === filter)
  return [...shown].sort((a, b) => TEMPERATURES.indexOf(a.temperature) - TEMPERATURES.indexOf(b.temperature))
}

/** "Asked for a meeting · Nov 8": why it has its temperature, and since when. */
export function temperatureLine(account: LaceAccountDto): string | null {
  if (!account.temperature_reason) return null
  const when = account.temperature_changed_at
    ? new Date(account.temperature_changed_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })
    : null
  return when ? `${account.temperature_reason} · ${when}` : account.temperature_reason
}

/** Each saved account's temperature, by id, for showing on its people. */
export function temperaturesById(accounts: LaceAccountDto[]): Map<string, LeadTemperature> {
  return new Map(accounts.map((a) => [a.id, a.temperature]))
}

/** A collapsed lead's one line: why it is warm or hot, else why now, else what it does. */
export function leadLine(account: LaceAccountDto): string | null {
  return temperatureLine(account)
    ?? (account.trigger ? `Why now: ${account.trigger.event}` : null)
    ?? account.summary
}
