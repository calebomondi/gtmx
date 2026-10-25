import { Label } from "@/components/ui/label"
import { PLATFORM_LABEL } from "@/lib/platforms"

import { AppSettingField } from "./app-setting-field"
import type { LaceApps } from "./use-lace-apps"

// Where each app takes the brief: its setting, the field's wording.
const DESTINATIONS = [
  { platform: "slack", setting: "brief_channel", label: "Post it in Slack", placeholder: "#sales", prefix: "#",
    missing: "post the brief in a Slack channel" },
  { platform: "notion", setting: "brief_page", label: "Save it in Notion, under", placeholder: "Notion page link",
    prefix: "", missing: "save each brief as a Notion page" },
] as const

function Destination({ apps, destination }: { apps: LaceApps; destination: (typeof DESTINATIONS)[number] }) {
  const app = apps.apps?.find((a) => a.platform === destination.platform)
  if (!app) return null
  if (!app.connected || !app.enabled) {
    return (
      <p className="text-xs text-muted-foreground">
        Connect {PLATFORM_LABEL[destination.platform]} under Apps &amp; accounts to {destination.missing}.
      </p>
    )
  }
  return <AppSettingField apps={apps} app={app} setting={destination.setting} label={destination.label}
                          placeholder={destination.placeholder} prefix={destination.prefix} clearLabel="Stop" />
}

/** Where else each brief goes, beside the chat and email: a Slack channel
 * and a Notion page. Setting one is the founder's standing approval. */
export function LaceBriefApps({ apps }: { apps: LaceApps }) {
  return (
    <section className="flex flex-col gap-3">
      <Label>Also send the brief</Label>
      {DESTINATIONS.map((d) => <Destination key={d.platform} apps={apps} destination={d} />)}
    </section>
  )
}
