import { useState } from "react"
import { Link } from "react-router-dom"
import { Layers, Loader2, Plus } from "lucide-react"

import { PlatformIcon } from "@/components/platform-icon"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { ConnectSteps } from "@/components/connect-steps"
import { CONNECT_STEPS, beginConnection, PLATFORM_LABEL, type Platform } from "@/lib/platforms"
import { cn } from "@/lib/utils"

import { LaceChannels } from "./lace-channels"
import { MESSAGING_PLATFORMS, type AccountKey, type MessagingAccount } from "./messaging-accounts"
import type { Connections } from "./use-connections"

const STATE_TEXT: Record<MessagingAccount["state"], string> = {
  connected: "Connected", attention: "Needs you to sign in again", none: "Not connected: you send these yourself",
}

/** One account as a round icon: what waits on it as a badge on its corner,
 * an amber dot when it needs signing in again; its name in the tooltip. */
function AccountIcon({ active, onClick, label, waiting, attention, children }: {
  active: boolean
  onClick: () => void
  label: string
  waiting: number
  attention?: boolean
  children: React.ReactNode
}) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active} title={label}
            aria-label={waiting ? `${label}, ${waiting} waiting` : label}
            className={cn("relative grid size-9 shrink-0 cursor-pointer place-items-center rounded-full border transition-colors",
                          active ? "border-theme/70 bg-theme/15 shadow-sm"
                                 : "border-border bg-background/60 hover:border-theme/40")}>
      {children}
      {waiting > 0 && (
        <span className="absolute -top-1.5 -right-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-theme px-1 text-[10px] font-semibold text-neutral-900 tabular-nums ring-2 ring-background">
          {waiting}
        </span>
      )}
      {attention && !waiting && (
        <span aria-hidden className="absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full bg-amber-500 ring-2 ring-background" />
      )}
    </button>
  )
}

/** Connecting the accounts outreach goes through, from Messaging (each
 * comes back here), and the business inboxes the Lace reads. */
function ConnectDialog({ laceId, name, connections, open, onOpenChange }: {
  laceId: string
  name: string
  connections: Connections
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [starting, setStarting] = useState<Platform | null>(null)
  const [error, setError] = useState<string | null>(null)
  // An app shown its steps first (Telegram's bot token), waiting for Continue.
  const [stepsFor, setStepsFor] = useState<Platform | null>(null)
  const connect = async (platform: Platform) => {
    setStarting(platform)
    setError(null)
    try {
      await beginConnection(platform, `/lace/${laceId}/messaging`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStarting(null)
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85svh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Accounts for outreach</DialogTitle>
          <DialogDescription>
            {name} drafts on these; nothing is sent until you send it. You come back here after connecting.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4 px-4 pb-4">
        <ul className="flex flex-col gap-2">
          {MESSAGING_PLATFORMS.map((platform) => {
            const connection = connections.connections.find((c) => c.platform === platform)
            const ready = connections.channels.some((c) => c.platform === platform && c.available)
            return (
              <li key={platform} className="flex flex-wrap items-center gap-3 rounded-xl border px-3 py-2.5">
                <PlatformIcon platform={platform} className="size-6" />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-sm font-medium">{PLATFORM_LABEL[platform]}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {connection
                      ? `${connection.status === "live" ? "Connected" : "Needs attention"}${connection.display_name ? ` as ${connection.display_name}` : ""}`
                      : ready ? "Not connected" : "Not available yet"}
                  </span>
                </span>
                {connection ? (
                  <Button size="sm" variant="ghost" render={<Link to="/accounts" />}>Manage</Button>
                ) : (
                  <Button size="sm" disabled={!ready || starting !== null}
                          onClick={() => (CONNECT_STEPS[platform] && stepsFor !== platform
                            ? setStepsFor(platform) : void connect(platform))}>
                    {starting === platform ? <Loader2 className="animate-spin" /> : <Plus />}
                    {stepsFor === platform ? " Continue" : " Connect"}
                  </Button>
                )}
                {stepsFor === platform && !connection && (
                  <div className="basis-full"><ConnectSteps platform={platform} /></div>
                )}
              </li>
            )
          })}
        </ul>
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        <Separator />
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">Inboxes {name} reads</h3>
          <p className="text-xs text-muted-foreground">Business accounts whose messages {name} reads and drafts answers to.</p>
          <LaceChannels laceId={laceId} />
        </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/** Pick which account Messaging shows (all, or one connected account), and
 * connect more without leaving the Lace. */
export function LaceAccountSwitcher({ laceId, name, accounts, value, onChange, totalWaiting, connections }: {
  laceId: string
  name: string
  accounts: MessagingAccount[]
  value: AccountKey
  onChange: (next: AccountKey) => void
  totalWaiting: number
  connections: Connections
}) {
  const [connecting, setConnecting] = useState(false)
  return (
    <div className="flex items-center gap-2">
      {/* Room around each icon for its badge, which sits over the edge. */}
      <div className="flex min-w-0 flex-1 items-center gap-2.5 overflow-x-auto px-1.5 py-1.5 [scrollbar-width:none]" role="group" aria-label="Accounts">
      <AccountIcon active={value === "all"} onClick={() => onChange("all")} label="All accounts" waiting={totalWaiting}>
        <Layers className="size-4" />
      </AccountIcon>
      {accounts.map((account) => (
        <AccountIcon key={account.key} active={value === account.key} onClick={() => onChange(account.key)}
                     label={[account.label, account.detail, STATE_TEXT[account.state]].filter(Boolean).join(" · ")}
                     waiting={account.waiting} attention={account.state === "attention"}>
          <PlatformIcon platform={account.platform} className="size-5" />
        </AccountIcon>
      ))}
      </div>
      <Button size="sm" variant="outline" className="shrink-0 rounded-full" onClick={() => setConnecting(true)}>
        {connections.loading ? <Loader2 className="animate-spin" /> : <Plus />} Connect
      </Button>
      <ConnectDialog laceId={laceId} name={name} connections={connections} open={connecting} onOpenChange={setConnecting} />
    </div>
  )
}
