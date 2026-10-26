import { useState } from "react"
import { ChevronDown, Loader2, Lock, Plus } from "lucide-react"

import { ConnectSteps } from "@/components/connect-steps"
import { PlatformIcon } from "@/components/platform-icon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import type { AppActionDto, LaceAppDto } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"
import {
  APP_GROUPS, COMING_SOON, CONNECT_STEPS, HANDLE_READS, PLATFORM_LABEL, beginConnection, beginLaceConnection,
} from "@/lib/platforms"
import { cn } from "@/lib/utils"

import { capabilitiesFor } from "../connected-accounts/accounts-type"
import { AppSettingField } from "./app-setting-field"
import { ActionCard } from "./lace-action-card"
import type { LaceApps } from "./use-lace-apps"
import type { LaceChat } from "./use-lace-chat"

const HISTORY_SHOWN = 10
const SAID: Record<string, string> = { done: "Done", failed: "Didn’t go through", declined: "Declined", running: "Running" }

function statusLine(app: LaceAppDto, name: string): string {
  if (!app.connected) {
    if (HANDLE_READS[app.platform]) {
      return app.settings.handle ? `Reading @${app.settings.handle}` : "Add your handle below"
    }
    if (!app.available) return "Not available yet"
    return app.status === "needs_attention" ? "Needs attention: reconnect it" : "Not connected"
  }
  const whose = app.account === "own" ? `${name}'s own` : "Shared"
  const who = app.account_name ? `${whose} · ${app.account_name}` : whose
  return app.enabled ? who : `${who} · switched off for ${name}`
}

/** Which account the Lace uses for the app, and a way to give it its own
 * (a founder whose startups each have their own email and socials) or go
 * back to the shared one. */
function AccountChoice({ app, name, onConnectOwn, onDisconnectOwn }: {
  app: LaceAppDto
  name: string
  onConnectOwn: () => void
  onDisconnectOwn: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  if (app.account === "own") {
    return (
      <div className="flex flex-wrap items-center gap-2 border-t px-3 py-2.5 text-xs">
        <p className="min-w-0 flex-1 text-muted-foreground">
          {name} uses its own {PLATFORM_LABEL[app.platform]} account; your other Laces don't.
        </p>
        {app.status === "needs_attention" && (
          <Button size="xs" variant="outline" onClick={onConnectOwn}>Reconnect</Button>
        )}
        <Button size="xs" variant={confirming ? "destructive" : "ghost"}
                onClick={() => (confirming ? onDisconnectOwn() : setConfirming(true))}>
          {confirming ? "Disconnect, use shared" : `Disconnect ${name}'s own`}
        </Button>
      </div>
    )
  }
  return (
    <div className="flex flex-wrap items-center gap-2 border-t px-3 py-2.5 text-xs">
      <p className="min-w-0 flex-1 text-muted-foreground">
        {app.account === "shared"
          ? "Your shared account: every Lace without its own uses it."
          : `Connect a shared account for all your Laces, or one just for ${name}.`}
      </p>
      <Button size="xs" variant="outline" onClick={onConnectOwn}>Use a separate account for {name}</Button>
    </div>
  )
}

/** One app: what it is to this Lace, a switch once connected, what the Lace
 * does with it, which account it uses, and a way to connect one without
 * leaving the Lace (after any steps the app needs first, like Telegram's bot
 * token). X and TikTok are also read by the founder's handle, with nothing
 * connected. */
function AppRow({ app, apps, laceId, name, onToggle, onDisconnectOwn }: {
  app: LaceAppDto
  apps: LaceApps
  laceId: string
  name: string
  onToggle: (enabled: boolean) => void
  onDisconnectOwn: () => void
}) {
  const [connecting, setConnecting] = useState(false)
  // The connection waiting on the app's steps (shared, or this Lace's own).
  const [steps, setSteps] = useState<"shared" | "own" | null>(null)
  const go = async (begin: () => Promise<void>) => {
    setConnecting(true)
    try {
      await begin()
    } catch {
      setConnecting(false)
    }
  }
  const begin = (which: "shared" | "own") => void go(() => which === "own"
    ? beginLaceConnection(laceId, app.platform)
    : beginConnection(app.platform, `/lace/${laceId}`))
  const start = (which: "shared" | "own") => (CONNECT_STEPS[app.platform] ? setSteps(which) : begin(which))
  const reads = HANDLE_READS[app.platform]
  return (
    <Collapsible className="rounded-xl border bg-card">
      <div className="flex items-center gap-3 p-3">
        <PlatformIcon platform={app.platform} className="size-7" />
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-sm font-medium">
            {PLATFORM_LABEL[app.platform]}
            {COMING_SOON.has(app.platform) && <Badge variant="outline" className="text-[10px]">Soon</Badge>}
          </p>
          <p className={cn("truncate text-xs", (app.connected && app.enabled) || (reads && app.settings.handle)
            ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground")}>
            {statusLine(app, name)}
          </p>
        </div>
        {app.connected ? (
          <Switch checked={app.enabled} onCheckedChange={onToggle} aria-label={`Let ${name} use ${PLATFORM_LABEL[app.platform]}`} />
        ) : app.available ? (
          <Button size="sm" variant="outline" onClick={() => start("shared")} disabled={connecting}>
            {connecting ? <Loader2 className="animate-spin" /> : <Plus />} Connect
          </Button>
        ) : (
          <Button size="sm" variant="outline" disabled
                  title={reads ? "Posting and messages need developer access, which isn't set up yet."
                    : `${PLATFORM_LABEL[app.platform]} isn't available yet.`}>
            <Lock /> Connect
          </Button>
        )}
        <CollapsibleTrigger render={
          <Button size="icon-sm" variant="ghost" aria-label={`What ${name} does with ${PLATFORM_LABEL[app.platform]}`} className="group/more" />
        }>
          <ChevronDown className="transition-transform group-data-[panel-open]/more:rotate-180" />
        </CollapsibleTrigger>
      </div>
      {reads && (
        <div className="flex flex-col gap-1 border-t px-3 py-2.5">
          <AppSettingField apps={apps} app={app} setting="handle" label="Your public profile" prefix="@"
                           placeholder="@yourhandle or a profile link" />
          <p className="text-xs text-muted-foreground">{name} reads {reads} from it, with nothing connected.</p>
        </div>
      )}
      <CollapsibleContent>
        <ul className="flex flex-col gap-1 border-t px-3 py-2.5 text-xs">
          {capabilitiesFor(app.platform).map((cap) => (
            <li key={cap.label} className={cn(cap.allowed ? "text-foreground" : "text-muted-foreground line-through")}>
              {cap.allowed ? "✓" : "✗"} {cap.label}
            </li>
          ))}
        </ul>
        {app.available && (
          <AccountChoice app={app} name={name} onConnectOwn={() => start("own")} onDisconnectOwn={onDisconnectOwn} />
        )}
      </CollapsibleContent>
      <Dialog open={steps !== null} onOpenChange={(open) => !open && setSteps(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Connect {PLATFORM_LABEL[app.platform]}</DialogTitle>
            <DialogDescription>
              {steps === "own" ? `An account just for ${name}.` : "A shared account, for all your Laces."}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 px-4 pb-4">
            <ConnectSteps platform={app.platform} />
            <Button disabled={connecting} onClick={() => steps && begin(steps)}>
              {connecting && <Loader2 className="animate-spin" />} Continue to connect
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Collapsible>
  )
}

function History({ actions }: { actions: AppActionDto[] }) {
  const done = actions.filter((a) => a.status !== "proposed").slice(0, HISTORY_SHOWN)
  if (done.length === 0) return null
  return (
    <section className="flex flex-col gap-2">
      <h4 className="text-xs font-semibold">What it did</h4>
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

/** Actions the Lace proposed in the founder's apps, waiting for their
 * approval: shown on the Feed, where what needs them is. */
export function LaceActionsWaiting({ chat, apps }: { chat: LaceChat; apps: LaceApps }) {
  const waiting = apps.actions.filter((a) => a.status === "proposed")
  if (waiting.length === 0) return null
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Waiting for your approval</p>
      {waiting.map((a) => (
        <ActionCard key={a.id} chat={chat} onDecided={apps.refresh}
                    block={{ type: "action", id: a.id, app: a.app, title: a.title, preview: a.preview, status: a.status }} />
      ))}
    </div>
  )
}

/** The Lace's apps, in its settings: every app by what the Lace does with
 * it (switch, connect, what it can do), and what it did in them. */
export function LaceAppsSection({ laceId, name, apps }: { laceId: string; name: string; apps: LaceApps }) {
  return (
    <div className="flex flex-col gap-5">
      {apps.error && <p className="text-sm text-destructive" role="alert">{apps.error}</p>}
      {APP_GROUPS.map((group) => (
        <div key={group.key} className="flex flex-col gap-2">
          <div>
            <h4 className="text-xs font-semibold">{group.label}</h4>
            <p className="text-xs text-muted-foreground">{group.blurb}</p>
          </div>
          {apps.apps
            ? apps.apps.filter((a) => a.group === group.key).map((app) => (
                <AppRow key={app.platform} app={app} apps={apps} laceId={laceId} name={name}
                        onToggle={(enabled) => void apps.setEnabled(app.platform, enabled)}
                        onDisconnectOwn={() => void apps.disconnectOwn(app)} />
              ))
            : group.platforms.map((p) => <Skeleton key={p} className="h-14 rounded-xl" />)}
        </div>
      ))}
      <History actions={apps.actions} />
    </div>
  )
}
