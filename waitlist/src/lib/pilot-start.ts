/** When the pilot starts, as the page says it: "October 24", and whether
 * that day has come. The date is a calendar day, so it is read in UTC and
 * never shifts with the visitor's time zone. */
export function pilotStart(startsOn: string, today = new Date()): { day: string; started: boolean } {
  const start = new Date(`${startsOn}T00:00:00Z`)
  const day = start.toLocaleDateString('en-US', { month: 'long', day: 'numeric', timeZone: 'UTC' })
  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate())
  return { day, started: start.getTime() <= todayUtc }
}
