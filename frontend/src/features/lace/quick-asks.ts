import type { LaceAppDto } from "@/lib/api"
import type { Platform } from "@/lib/platforms"

export interface QuickAsk {
  platform: Platform
  /** What the chip says. */
  label: string
  /** The message sent to the Lace. */
  text: string
}

// One-tap asks per app, each backed by the Lace's tools for that app.
const ASKS: Partial<Record<Platform, Omit<QuickAsk, "platform">[]>> = {
  zoho: [{ label: "Summarise my pipeline", text: "Summarise my CRM pipeline: deals by stage, what's stale, and what's closing soon." },
         { label: "Which deals went quiet?", text: "Which open deals in my CRM have gone quiet, and what should I do about each?" }],
  hubspot: [{ label: "Summarise my pipeline", text: "Summarise my CRM pipeline: deals by stage, what's stale, and what's closing soon." },
            { label: "Which deals went quiet?", text: "Which open deals in my CRM have gone quiet, and what should I do about each?" }],
  googlesheets: [{ label: "Export accounts to Sheets", text: "Export my saved target accounts to a new Google Sheet." },
                 { label: "Export contacts to Sheets", text: "Export my contacts to a new Google Sheet." }],
  asana: [{ label: "What's overdue in Asana?", text: "What's overdue or due this week in my Asana tasks?" }],
  calendly: [{ label: "Who booked a meeting?", text: "Who booked a meeting on my Calendly in the last week and the next two, and are any of them my contacts?" }],
  slack: [{ label: "What did the team say?", text: "Search our Slack for what the team said about my target accounts lately." }],
  notion: [{ label: "Find our pricing in Notion", text: "Find our pricing in Notion and tell me what it says." }],
  instagram: [{ label: "Who commented on my posts?", text: "Who commented on my recent Instagram posts? Point out any worth reaching out to." }],
  facebook: [{ label: "Who commented on my Page?", text: "Who commented on my Facebook Page's recent posts? Point out any worth reaching out to." }],
  linkedin: [{ label: "Draft a LinkedIn post", text: "Draft a LinkedIn post about what we did this week." }],
}
// The CRMs share their asks: only the one the Lace uses is offered.
const CRMS: Platform[] = ["zoho", "hubspot"]

/** The quick asks for the apps a Lace can use now (connected and switched on), in app order. */
export function quickAsks(apps: LaceAppDto[] | null): QuickAsk[] {
  const usable = (apps ?? []).filter((a) => a.connected && a.enabled)
  const crm = CRMS.find((p) => usable.some((a) => a.platform === p))
  return usable
    .filter((a) => !CRMS.includes(a.platform) || a.platform === crm)
    .flatMap((a) => (ASKS[a.platform] ?? []).map((ask) => ({ ...ask, platform: a.platform })))
}
