import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PLATFORM_LABEL } from "@/lib/platforms"

import type { LaceApps } from "./use-lace-apps"

// Where each app takes the brief: its setting, the field's wording.
const DESTINATIONS = [
  { platform: "slack", setting: "brief_channel", label: "Post it in Slack", placeholder: "#sales",
    missing: "post the brief in a Slack channel" },
  { platform: "notion", setting: "brief_page", label: "Save it in Notion, under", placeholder: "Notion page link",
    missing: "save each brief as a Notion page" },
] as const

function Destination({ apps, destination }: { apps: LaceApps; destination: (typeof DESTINATIONS)[number] }) {
  const app = apps.apps?.find((a) => a.platform === destination.platform)
  const saved = app?.settings[destination.setting] ?? ""
  const [value, setValue] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const id = `brief-${destination.platform}`
  if (!app) return null
  if (!app.connected || !app.enabled) {
    return (
      <p className="text-xs text-muted-foreground">
        Connect {PLATFORM_LABEL[destination.platform]} under Apps &amp; accounts to {destination.missing}.
      </p>
    )
  }
  const shown = value ?? (destination.platform === "slack" && saved ? `#${saved}` : saved)
  const save = async (next: string) => {
    setSaving(true)
    if (await apps.setSettings(destination.platform, { ...app.settings, [destination.setting]: next })) setValue(null)
    setSaving(false)
  }
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{destination.label}</Label>
      <div className="flex gap-2">
        <Input id={id} value={shown} placeholder={destination.placeholder} onChange={(e) => setValue(e.target.value)} />
        <Button size="sm" variant="outline" disabled={saving || value === null} onClick={() => void save(value ?? "")}>
          Save
        </Button>
        {saved && value === null && (
          <Button size="sm" variant="ghost" disabled={saving} onClick={() => void save("")}>Stop</Button>
        )}
      </div>
    </div>
  )
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
