"use client"

import * as React from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { Skeleton } from "@/components/ui/skeleton"
import { ALL_PLATFORMS, APP_GROUPS, PLATFORM_LABEL, type Platform } from "@/lib/platforms"
import { cn } from "@/lib/utils"

import { AccountTile, type GridItem } from "./account-tile"
import { disconnectConnection, fetchConnectionState, type Connection } from "./accounts-type"
import { ConnectionDialog, type DialogState } from "./connection-dialog"

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

  const itemsFor = (platforms: Platform[]): GridItem[] => connections
    ? platforms.flatMap<GridItem>((platform) => {
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
            <h1 className="mt-1 text-2xl font-semibold">Shared accounts</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Every Lace of yours uses these, unless you give one its own account in its settings. It acts in them only
              when you approve.
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
              ? `${liveCount} of ${ALL_PLATFORMS.length} apps live`
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
            No apps connected yet. Connect your email first, so your Lace can reach out.
          </p>
        )}

        {APP_GROUPS.map((group, g) => (
          <section key={group.key} className="mt-8" aria-labelledby={`group-${group.key}`}>
            <h2 id={`group-${group.key}`} className="text-sm font-semibold">{group.label}</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">{group.blurb}</p>
            <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
              {connections
                ? itemsFor(group.platforms).map((item, i) => (
                    <AccountTile
                      key={item.kind === "connection" ? item.connection.id : `available-${item.platform}`}
                      item={item}
                      index={g * 4 + i}
                      onOpen={(it) =>
                        setDialog(
                          it.kind === "connection"
                            ? { target: it.connection, view: "manage" }
                            : { target: it.platform, view: "connect" },
                        )
                      }
                    />
                  ))
                : group.platforms.map((p) => <Skeleton key={p} className="h-40 rounded-xl" />)}
            </div>
          </section>
        ))}
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
