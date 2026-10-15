"use client"

import * as React from "react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import {
  AlertTriangle,
  Check,
  Minus,
  RefreshCw,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"
import {
  ALL_PLATFORMS,
  PLATFORM_LABEL,
  REPLY_ONLY_NOTE,
  capabilitiesFor,
  beginConnection,
  disconnectConnection,
  fetchConnectionState,
  type Connection,
  type Platform,
} from "./accounts-type"
import { PlatformIcon } from "./platform-icon"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return "just now"
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

// ---------------------------------------------------------------------------
// Tile
// ---------------------------------------------------------------------------

type GridItem =
  | { kind: "connection"; connection: Connection }
  | { kind: "available"; platform: Platform; ready: boolean }

function AccountTile({
  item,
  index,
  onOpen,
}: {
  item: GridItem
  index: number
  onOpen: (item: GridItem) => void
}) {
  const reduceMotion = useReducedMotion()
  const connection = item.kind === "connection" ? item.connection : null
  const platform = item.kind === "connection" ? item.connection.platform : item.platform
  const live = connection?.status === "live"

  return (
    <motion.article
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: reduceMotion ? 0 : index * 0.05, ease: "easeOut" }}
      onClick={(e) => {
        // The ⋮ menu owns its own clicks; anything else opens the dialog.
        if ((e.target as HTMLElement).closest("button")) return
        onOpen(item)
      }}
      className={cn(
        "group relative flex h-4[auto] cursor-pointer flex-col overflow-hidden rounded-xl border p-3 transition-colors outline-none shadow-sm",
        "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
        connection
          ? "border-[#B7E4CC] bg-[#EFFAF3] dark:border-[#1E3A2C] dark:bg-[#0E1F17]"
          : "border-dashed border-border/70 hover:border-foreground/30 hover:bg-muted/40",
      )}
      tabIndex={0}
      role="button"
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onOpen(item)
        }
      }}
      aria-label={
        connection
          ? `Manage ${PLATFORM_LABEL[platform]} connection for ${connection.username}`
          : `Connect ${PLATFORM_LABEL[platform]}`
      }
    >
      {connection && (
        <span
          className={cn(
            "pointer-events-none absolute top-1 left-1/2 h-[4px] w-8 -translate-x-1/2 rounded-full",
            live ? "bg-emerald-500" : connection.status === "pending" ? "bg-muted-foreground/50" : "bg-amber-500",
          )}
        />
      )}

      {/* <div className="flex items-start justify-end bg-red-100">
        {connection && (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="size-7 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 data-[state=open]:opacity-100"
                  aria-label="Connection actions"
                />
              }
            >
              <MoreHorizontal />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" sideOffset={6}>
              <DropdownMenuItem onClick={() => onOpen(item)}>
                <Link2 /> Manage connection
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onClick={() => onDisconnect(connection)}
              >
                <Plug /> Disconnect
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div> */}
      <div className="flex justify-center flex-col items-center">
        <PlatformIcon platform={platform} className="mt-2" />
        <div className="min-w-0 pb-2">
            {connection ? (
            <>
                <p className="truncate text-xs font-medium">{connection.username}</p>
                {connection.displayName && (
                <p className="truncate text-[11px] text-muted-foreground">
                    {connection.displayName}
                </p>
                )}
            </>
            ) : (
            <p className="text-xs text-muted-foreground transition-colors group-hover:text-[#FEA853]">
                {item.kind === "available" && !item.ready ? "Setup required" : "Connect"}
            </p>
            )}
        </div>
      </div>

    </motion.article>
  )
}

// ---------------------------------------------------------------------------
// Dialog (manage / connect / confirm)
// ---------------------------------------------------------------------------

type DialogState =
  | { target: Connection; view: "manage" | "confirm" }
  | { target: Platform; view: "connect" }

function CapabilityRow({ label, allowed }: { label: string; allowed: boolean }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      {allowed ? (
        <Check className="size-4 shrink-0 text-emerald-500" />
      ) : (
        <Minus className="size-4 shrink-0 text-muted-foreground/60" />
      )}
      <span className={allowed ? "" : "text-muted-foreground/70"}>{label}</span>
    </li>
  )
}

function ConnectionDialog({
  state,
  onClose,
  onNavigate,
  onDisconnect,
  ready,
}: {
  state: DialogState
  onClose: () => void
  onNavigate: (view: "manage" | "confirm") => void
  onDisconnect: (connection: Connection) => void
  /** Whether this channel can be connected now (app-level OAuth exists). */
  ready: boolean
}) {
  const reduceMotion = useReducedMotion()
  const [working, setWorking] = React.useState(false)

  const isConnect = state.view === "connect"
  const connection = isConnect ? null : (state as { target: Connection }).target
  const platform = isConnect ? (state as { target: Platform }).target : connection!.platform

  const connect = async () => {
    if (working || !ready) return
    setWorking(true)
    try {
      await beginConnection(platform)  // navigates away on success
    } catch (err) {
      toast.error(`Couldn't start connecting ${PLATFORM_LABEL[platform]}`, {
        description: err instanceof Error ? err.message : String(err),
      })
      setWorking(false)
    }
  }

  const direction = state.view === "confirm" ? 1 : -1

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg p-0">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={state.view}
            initial={{ opacity: 0, x: reduceMotion ? 0 : direction * 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: reduceMotion ? 0 : direction * -16 }}
            transition={{ duration: reduceMotion ? 0 : 0.16, ease: "easeOut" }}
          >
            {/* --- header --- */}
            <div className="flex items-start gap-3 px-5 pt-5 pb-4">
              <PlatformIcon platform={platform} />
              <div className="min-w-0 flex-1">
                <DialogTitle className="text-base">
                  {state.view === "confirm"
                    ? `Disconnect ${PLATFORM_LABEL[platform]}?`
                    : isConnect
                      ? `Connect ${PLATFORM_LABEL[platform]}`
                      : PLATFORM_LABEL[platform]}
                </DialogTitle>
                <DialogDescription className="truncate text-xs">
                  {state.view === "confirm"
                    ? `The agent will no longer be able to act through ${
                        connection?.username ?? PLATFORM_LABEL[platform]
                      }.`
                    : isConnect
                      ? "You'll be redirected to sign in with the platform."
                      : connection
                        ? [
                            connection.username,
                            `Connected ${shortDate(connection.connectedAt)}`,
                            `Synced ${timeAgo(connection.lastSync)}`,
                          ].join(" · ")
                        : PLATFORM_LABEL[platform]}
                </DialogDescription>
              </div>
              {connection && state.view === "manage" && (
                <span
                  className={cn(
                    "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                    connection.status === "live"
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                      : "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
                  )}
                >
                  <span
                    className={cn(
                      "size-1.5 rounded-full",
                      connection.status === "live" ? "bg-emerald-500" : "bg-amber-500",
                    )}
                  />
                  {connection.status === "live" ? "Live" : connection.status === "pending" ? "Pending" : "Needs attention"}
                </span>
              )}
            </div>

            <Separator />

            {/* --- body --- */}
            <div className="px-5 py-4">
              {state.view === "confirm" ? (
                <div className="flex gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
                  <p className="text-sm">
                    Sent messages and history stay in your workspace — only the
                    live link is removed. You can reconnect at any time.
                  </p>
                </div>
              ) : isConnect ? (
                <div className="space-y-3 text-sm">
                  <p className="text-muted-foreground">
                    The agent will be able to use this channel for outreach
                    once you've signed in. Nothing is ever sent without your
                    approval.
                  </p>
                  {REPLY_ONLY_NOTE[platform] && (
                    <div className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-foreground">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" />
                      <p>{REPLY_ONLY_NOTE[platform]}</p>
                    </div>
                  )}
                  <ul className="space-y-1.5">
                    {capabilitiesFor(platform).map((cap) => (
                      <CapabilityRow key={cap.label} label={cap.label} allowed={cap.allowed} />
                    ))}
                  </ul>
                  {!ready && (
                    <p className="text-xs text-amber-600 dark:text-amber-400">
                      {PLATFORM_LABEL[platform]} needs a one-time app setup by
                      the GTMX team before it can be connected.
                    </p>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  {connection!.status === "pending" && (
                    <div className="flex items-start gap-2 rounded-lg border border-border p-3 text-sm text-muted-foreground">
                      <RefreshCw className="mt-0.5 size-4 shrink-0" />
                      <p>Sign-in hasn't finished. Reconnect to try again.</p>
                    </div>
                  )}
                  {connection!.status === "needs_attention" && (
                    <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" />
                      <p>
                        This connection needs to be reauthorized before the
                        agent can use it.
                      </p>
                    </div>
                  )}
                  <div>
                    <p className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                      What the agent can do
                    </p>
                    <ul className="space-y-1.5">
                      {connection!.capabilities.map((cap) => (
                        <CapabilityRow key={cap.label} {...cap} />
                      ))}
                    </ul>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Used in {connection!.usageCount}{" "}
                    {connection!.usageCount === 1 ? "outreach run" : "outreach runs"}
                  </p>
                </div>
              )}
            </div>

            <Separator />

            {/* --- footer --- */}
            <div className="flex justify-end gap-2 px-5 py-4">
              {state.view === "confirm" ? (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onNavigate("manage")}
                  >
                    Keep connection
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => {
                      onDisconnect(connection!)
                      onClose()
                    }}
                  >
                    Disconnect
                  </Button>
                </>
              ) : isConnect ? (
                <>
                  <Button variant="outline" size="sm" onClick={onClose}>
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    disabled={working || !ready}
                    onClick={() => void connect()}
                  >
                    {working && (
                      <RefreshCw className="mr-1.5 size-3.5 animate-spin" />
                    )}
                    Continue with {PLATFORM_LABEL[platform]}
                  </Button>
                </>
              ) : (
                <>
                  <Button variant="outline" size="sm" disabled={working || !ready} onClick={() => void connect()}>
                    <RefreshCw
                      className={cn(
                        "mr-1.5 size-3.5",
                        working && "animate-spin",
                      )}
                    />
                    Reconnect
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => onNavigate("confirm")}
                  >
                    Disconnect
                  </Button>
                </>
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AccountsComponent() {
  const [connections, setConnections] = React.useState<Connection[] | null>(null)
  const [available, setAvailable] = React.useState<Set<Platform>>(new Set())
  const [dialog, setDialog] = React.useState<DialogState | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()

  React.useEffect(() => {
    let cancelled = false
    // Back from a provider sign-in: the server re-lists from Composio, so the
    // query string itself is never trusted -- it only picks the toast.
    const returnedFrom = searchParams.get("connected") as Platform | null
    fetchConnectionState()
      .then((state) => {
        if (cancelled) return
        setConnections(state.connections)
        setAvailable(state.available)
        if (returnedFrom && returnedFrom in PLATFORM_LABEL) {
          const live = state.connections.some((c) => c.platform === returnedFrom && c.status === "live")
          if (live) toast.success(`${PLATFORM_LABEL[returnedFrom]} connected`)
          else toast.info(`${PLATFORM_LABEL[returnedFrom]} sign-in didn't finish`, { description: "Try connecting again." })
          setSearchParams({}, { replace: true })
        }
      })
      .catch(() => !cancelled && setConnections([]))
    return () => {
      cancelled = true
    }
  }, [searchParams, setSearchParams])

  const disconnect = async (connection: Connection) => {
    try {
      await disconnectConnection(connection.id)
      setConnections((prev) => prev?.filter((row) => row.id !== connection.id) ?? prev)
      toast.success(`${PLATFORM_LABEL[connection.platform]} disconnected`)
    } catch (err) {
      toast.error("Couldn't disconnect", { description: err instanceof Error ? err.message : String(err) })
    }
  }

  const items: GridItem[] = connections
    ? ALL_PLATFORMS.flatMap<GridItem>((platform) => {
        const connected = connections.filter((c) => c.platform === platform)
        return connected.length > 0
          ? connected.map((connection) => ({ kind: "connection", connection }))
          : [{ kind: "available", platform, ready: available.has(platform) }]
      })
    : []

  const connectedCount = connections?.length ?? 0
  const liveCount =
    connections?.filter((c) => c.status === "live").length ?? 0
  const attentionCount =
    connections?.filter((c) => c.status === "needs_attention").length ?? 0

  return (
    <div className="h-full overflow-y-auto bg-muted">
      <div className="mx-auto max-w-5xl px-6 py-8">
        {/* header */}
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            {/* <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
              Accounts
            </p> */}
            <h1 className="mt-1 text-2xl font-semibold">Connected accounts</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Channels the agent can use to reach out.
            </p>
          </div>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <span
              className={cn(
                "size-2 rounded-full",
                liveCount > 0 ? "bg-emerald-500" : "border border-border",
              )}
            />
            {connections
              ? `${liveCount} of ${ALL_PLATFORMS.length} channels live`
              : "Loading…"}
            {attentionCount > 0 && (
              <span className="text-amber-500">
                · {attentionCount} need{attentionCount === 1 ? "s" : ""} attention
              </span>
            )}
          </p>
        </div>

        {connections && connectedCount === 0 && (
          <p className="mt-6 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            No channels connected yet — connect one so the agent can reach out.
          </p>
        )}

        {/* grid */}
        <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
          {connections
            ? items.map((item, i) => (
                <AccountTile
                  key={
                    item.kind === "connection"
                      ? item.connection.id
                      : `available-${item.platform}`
                  }
                  item={item}
                  index={i}
                  onOpen={(it) =>
                    setDialog(
                      it.kind === "connection"
                        ? { target: it.connection, view: "manage" }
                        : { target: it.platform, view: "connect" },
                    )
                  }
                />
              ))
            : Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-40 rounded-xl" />
              ))}
        </div>
      </div>

      {dialog && (
        <ConnectionDialog
          key={
            typeof dialog.target === "string"
              ? `connect-${dialog.target}`
              : dialog.target.id
          }
          state={dialog}
          onClose={() => setDialog(null)}
          onNavigate={(view) => setDialog((prev) => (prev ? { ...prev, view } as DialogState : prev))}
          onDisconnect={(c) => void disconnect(c)}
          ready={available.has(typeof dialog.target === "string" ? dialog.target : dialog.target.platform)}
        />
      )}
    </div>
  )
}
