import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { LaceAppDto } from "@/lib/api"

import type { LaceApps } from "./use-lace-apps"

/** One setting of an app for this Lace (the brief's Slack channel, the
 * founder's TikTok handle): a field with Save, and Clear once set. The
 * server checks and tidies the value ("#Sales" → "sales"); `prefix` shows it
 * back the way people write it. */
export function AppSettingField({ apps, app, setting, label, placeholder, prefix = "", clearLabel = "Clear" }: {
  apps: LaceApps
  app: LaceAppDto
  setting: string
  label: string
  placeholder: string
  prefix?: string
  clearLabel?: string
}) {
  const saved = app.settings[setting] ?? ""
  const [value, setValue] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const id = `${app.platform}-${setting}`
  const save = async (next: string) => {
    setSaving(true)
    if (await apps.setSettings(app.platform, { ...app.settings, [setting]: next })) setValue(null)
    setSaving(false)
  }
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex gap-2">
        <Input id={id} value={value ?? (saved ? `${prefix}${saved}` : "")} placeholder={placeholder}
               onChange={(e) => setValue(e.target.value)} />
        <Button size="sm" variant="outline" disabled={saving || value === null} onClick={() => void save(value ?? "")}>
          Save
        </Button>
        {saved && value === null && (
          <Button size="sm" variant="ghost" disabled={saving} onClick={() => void save("")}>{clearLabel}</Button>
        )}
      </div>
    </div>
  )
}
