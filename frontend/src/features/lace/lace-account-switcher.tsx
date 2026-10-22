import { useState } from "react"
import { Link } from "react-router-dom"
import { Layers, Loader2, Plus } from "lucide-react"

import { PlatformIcon } from "@/components/platform-icon"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { beginConnection, PLATFORM_LABEL, type Platform } from "@/lib/platforms"
import { cn } from "@/lib/utils"

import { LaceChannels } from "./lace-channels"
import { MESSAGING_PLATFORMS, type AccountKey, type MessagingAccount } from "./messaging-accounts"
import type { Connections } from "./use-connections"

const STATE_DOT: Record<MessagingAccount["state"], string> = {
  connected: "bg-emerald-500", attention: "bg-amber-500", none: "border border-muted-foreground/50",
}
const STATE_TEXT: Record<MessagingAccount["state"], string> = {
  connected: "Connected", attention: "Needs you to sign in again", none: "Not connected: you send these yourself",
}

function Count({ n }: { n: number }) {
  if (n === 0) return null
  return (
    <span className="grid h-5 min-w-5 place-items-center rounded-full bg-theme px-1.5 text-[11px] font-medium text-neutral-900 tabular-nums">
      {n}
    </span>
  )
}

function Pill({ active, onClick, children, title }: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
  title?: string
}) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active} title={title}
            className={cn("flex shrink-0 cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors",
                          active ? "border-theme/60 bg-theme/15 text-foreground shadow-sm"
                                 : "border-border bg-background/60 text-muted-foreground hover:border-theme/40 hover:text-foreground")}>
      {children}
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
              <li key={platform} className="flex items-center gap-3 rounded-xl border px-3 py-2.5">
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
                  <Button size="sm" onClick={() => void connect(platform)} disabled={!ready || starting !== null}>
                    {starting === platform ? <Loader2 className="animate-spin" /> : <Plus />} Connect
                  </Button>
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
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto [scrollbar-width:none]" role="group" aria-label="Accounts">
      <Pill active={value === "all"} onClick={() => onChange("all")}>
        <Layers className="size-4" /> All accounts <Count n={totalWaiting} />
      </Pill>
      {accounts.map((account) => (
        <Pill key={account.key} active={value === account.key} onClick={() => onChange(account.key)}
              title={`${account.label}: ${STATE_TEXT[account.state]}`}>
          <PlatformIcon platform={account.platform} className="size-4" />
          <span>{account.label}</span>
          {/* Who it is only on the chosen one, so every account fits in a row. */}
          {account.detail && value === account.key && (
            <span className="max-w-40 truncate text-xs text-muted-foreground">{account.detail}</span>
          )}
          <span aria-hidden className={cn("size-1.5 rounded-full", STATE_DOT[account.state])} />
          <Count n={account.waiting} />
        </Pill>
      ))}
      </div>
      <Button size="sm" variant="outline" className="shrink-0 rounded-full" onClick={() => setConnecting(true)}>
        {connections.loading ? <Loader2 className="animate-spin" /> : <Plus />} Connect
      </Button>
      <ConnectDialog laceId={laceId} name={name} connections={connections} open={connecting} onOpenChange={setConnecting} />
    </div>
  )
}
