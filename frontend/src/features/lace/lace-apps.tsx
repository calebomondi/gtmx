import { useState } from "react"
import { ChevronDown, Loader2, Plus } from "lucide-react"

import { PlatformIcon } from "@/components/platform-icon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import type { AppActionDto, LaceAppDto } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"
import { APP_GROUPS, COMING_SOON, PLATFORM_LABEL, beginConnection } from "@/lib/platforms"
import { cn } from "@/lib/utils"

import { capabilitiesFor } from "../connected-accounts/accounts-type"
import { ActionCard } from "./lace-action-card"
import { PanelIntro } from "./lace-panel-tabs"
import type { LaceApps } from "./use-lace-apps"
import type { LaceChat } from "./use-lace-chat"

const HISTORY_SHOWN = 10
const SAID: Record<string, string> = { done: "Done", failed: "Didn’t go through", declined: "Declined", running: "Running" }

function statusLine(app: LaceAppDto, name: string): string {
  if (!app.connected) return app.status === "needs_attention" ? "Needs attention: reconnect it" : "Not connected"
  return app.enabled ? `Connected · ${name} can use it` : `Connected · switched off for ${name}`
}

/** One app: what it is to this Lace, a switch once connected, what the Lace
 * does with it, and a way to connect it without leaving the Lace. */
function AppRow({ app, laceId, name, onToggle }: {
  app: LaceAppDto
  laceId: string
  name: string
  onToggle: (enabled: boolean) => void
}) {
  const [connecting, setConnecting] = useState(false)
  const connect = async () => {
    setConnecting(true)
    try {
      await beginConnection(app.platform, `/lace/${laceId}/apps`)
    } catch {
      setConnecting(false)
    }
  }
  return (
    <Collapsible className="rounded-xl border bg-card">
      <div className="flex items-center gap-3 p-3">
        <PlatformIcon platform={app.platform} className="size-7" />
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-sm font-medium">
            {PLATFORM_LABEL[app.platform]}
            {COMING_SOON.has(app.platform) && <Badge variant="outline" className="text-[10px]">Soon</Badge>}
          </p>
          <p className={cn("truncate text-xs", app.connected && app.enabled ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground")}>
            {statusLine(app, name)}
          </p>
        </div>
        {app.connected ? (
          <Switch checked={app.enabled} onCheckedChange={onToggle} aria-label={`Let ${name} use ${PLATFORM_LABEL[app.platform]}`} />
        ) : (
          <Button size="sm" variant="outline" onClick={() => void connect()} disabled={connecting}>
            {connecting ? <Loader2 className="animate-spin" /> : <Plus />} Connect
          </Button>
        )}
        <CollapsibleTrigger render={
          <Button size="icon-sm" variant="ghost" aria-label={`What ${name} does with ${PLATFORM_LABEL[app.platform]}`} className="group/more" />
        }>
          <ChevronDown className="transition-transform group-data-[panel-open]/more:rotate-180" />
        </CollapsibleTrigger>
      </div>
      <CollapsibleContent>
        <ul className="flex flex-col gap-1 border-t px-3 py-2.5 text-xs">
          {capabilitiesFor(app.platform).map((cap) => (
            <li key={cap.label} className={cn(cap.allowed ? "text-foreground" : "text-muted-foreground line-through")}>
              {cap.allowed ? "✓" : "✗"} {cap.label}
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}

function History({ actions }: { actions: AppActionDto[] }) {
  const done = actions.filter((a) => a.status !== "proposed").slice(0, HISTORY_SHOWN)
  if (done.length === 0) return null
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">What it did</h2>
      <Card size="sm">
        <CardContent className="flex flex-col divide-y p-0">
          {done.map((a) => (
            <div key={a.id} className="flex items-start gap-3 px-3 py-2 text-sm">
              <PlatformIcon platform={a.app as LaceAppDto["platform"]} className="mt-0.5 size-5" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{a.title}</p>
                {a.result && <p className="truncate text-xs text-muted-foreground">{a.result}</p>}
              </div>
              <span className="shrink-0 text-right text-xs text-muted-foreground">
                {SAID[a.status] ?? a.status}
                <br />
                {formatRelativeTime(Date.parse(a.finished_at ?? a.decided_at ?? a.created_at))}
              </span>
            </div>
          ))}
        </CardContent>
      </Card>
    </section>
  )
}

/** The Lace's apps: what waits for the founder's approval, every app by what
 * the Lace does with it (switch, connect, what it can do), and what it did. */
export function LaceAppsTab({ laceId, name, chat, apps }: { laceId: string; name: string; chat: LaceChat; apps: LaceApps }) {
  const waiting = apps.actions.filter((a) => a.status === "proposed")
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-6">
      <PanelIntro>
        The apps {name} works in. It acts in them only when you approve, and only in the ones switched on here.
      </PanelIntro>

      {waiting.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold">Waiting for you</h2>
          {waiting.map((a) => (
            <ActionCard key={a.id} chat={chat} onDecided={apps.refresh}
                        block={{ type: "action", id: a.id, app: a.app, title: a.title, preview: a.preview, status: a.status }} />
          ))}
        </section>
      )}

      {apps.error && <p className="text-sm text-destructive" role="alert">{apps.error}</p>}
      {APP_GROUPS.map((group) => (
        <section key={group.key} className="flex flex-col gap-2">
          <div>
            <h2 className="text-sm font-semibold">{group.label}</h2>
            <p className="text-xs text-muted-foreground">{group.blurb}</p>
          </div>
          {apps.apps
            ? apps.apps.filter((a) => a.group === group.key).map((app) => (
                <AppRow key={app.platform} app={app} laceId={laceId} name={name}
                        onToggle={(enabled) => void apps.setEnabled(app.platform, enabled)} />
              ))
            : group.platforms.map((p) => <Skeleton key={p} className="h-14 rounded-xl" />)}
        </section>
      ))}

      <History actions={apps.actions} />
    </div>
  )
}
