import * as React from "react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { AlertTriangle, Check, Minus, RefreshCw } from "lucide-react"
import { toast } from "sonner"

import { PlatformIcon } from "@/components/platform-icon"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { useNavigate } from "react-router-dom"

import { ConnectSteps } from "@/components/connect-steps"
import { useLaces } from "@/lib/laces-store"
import { HANDLE_READS, PLATFORM_LABEL, beginConnection, type Platform } from "@/lib/platforms"
import { cn } from "@/lib/utils"

import { REPLY_ONLY_NOTE, capabilitiesFor, type Connection } from "./accounts-type"

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

export type DialogState =
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

export function ConnectionDialog({
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
  const navigate = useNavigate()
  const { laces } = useLaces()
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
                      ? ready
                        ? "You'll be redirected to sign in with the platform."
                        : HANDLE_READS[platform] ? "Read by your handle; connecting isn't set up yet." : "Not available yet."
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
                  {ready ? (
                    <p className="text-muted-foreground">
                      Your Lace will be able to use it once you've signed in. Nothing is ever sent without your
                      approval.
                    </p>
                  ) : HANDLE_READS[platform] ? (
                    <div className="space-y-2 rounded-lg border bg-muted/40 p-3">
                      <p>
                        Reading {HANDLE_READS[platform]} works now, from your handle: add it under Apps &amp; accounts →{" "}
                        {PLATFORM_LABEL[platform]} in each Lace's settings (each startup has its own).
                      </p>
                      <p className="text-muted-foreground">
                        Posting and messages through {PLATFORM_LABEL[platform]} need developer access, which isn't set
                        up yet.
                      </p>
                    </div>
                  ) : (
                    <p className="text-muted-foreground">{PLATFORM_LABEL[platform]} isn't available yet.</p>
                  )}
                  {ready && <ConnectSteps platform={platform} />}
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
                    {ready ? "Cancel" : "Close"}
                  </Button>
                  {ready ? (
                    <Button size="sm" disabled={working} onClick={() => void connect()}>
                      {working && <RefreshCw className="mr-1.5 size-3.5 animate-spin" />}
                      Continue with {PLATFORM_LABEL[platform]}
                    </Button>
                  ) : HANDLE_READS[platform] && laces.length === 1 ? (
                    <Button size="sm" onClick={() => navigate(`/lace/${laces[0].id}?settings=apps`)}>
                      Add it in {laces[0].name}'s settings
                    </Button>
                  ) : null}
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
