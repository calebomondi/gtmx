"use client"

import * as React from "react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { Info, Link, RefreshCw } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { Link as RouterLink } from "react-router-dom"
import { PlatformIcon } from "@/features/connected-accounts/platform-icon"
import {
  AGENT_IDENTITY,
  ALL_PLATFORMS,
  PLATFORM_LABEL,
  connectAgentConnection,
  fetchConnections,
  type Connection,
  type Platform,
} from "@/features/connected-accounts/accounts-type"

/**
 * Agent-level channel connections for the workspace's agent.
 *
 * The agent has its own identity per platform (separate OAuth). Until a
 * channel is connected for the agent, it sends through the user's
 * account-level connections (the /accounts board) by default.
 *
 * Mock only — agent connections live in local state until the backend lands.
 */

const SEED_AGENT_CONN: Connection = {
  id: "agent_gmail",
  platform: "gmail",
  username: AGENT_IDENTITY.gmail,
  status: "live",
  connectedAt: new Date(Date.now() - 12 * 864e5).toISOString(),
  lastSync: new Date().toISOString(),
  capabilities: [],
  usageCount: 2,
}

export function AgentConnectionsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const reduceMotion = useReducedMotion()
  const [accountCons, setAccountCons] = React.useState<Connection[] | null>(null)
  const [agentCons, setAgentCons] = React.useState<Connection[]>([SEED_AGENT_CONN])
  const [connecting, setConnecting] = React.useState<Platform | null>(null)

  React.useEffect(() => {
    if (!open) return
    let cancelled = false
    void fetchConnections().then((rows) => {
      if (!cancelled) setAccountCons(rows)
    })
    return () => {
      cancelled = true
    }
  }, [open])

  const byPlatform = React.useMemo(() => {
    const map = new Map<Platform, Connection[]>()
    for (const c of accountCons ?? []) {
      const list = map.get(c.platform) ?? []
      list.push(c)
      map.set(c.platform, list)
    }
    return map
  }, [accountCons])

  const connect = async (platform: Platform) => {
    if (connecting || agentCons.some((c) => c.platform === platform)) return
    setConnecting(platform)
    const conn = await connectAgentConnection(platform)
    setAgentCons((prev) => [...prev, conn])
    setConnecting(null)
  }

  const disconnect = (platform: Platform) =>
    setAgentCons((prev) => prev.filter((c) => c.platform !== platform))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl p-0">
        <div className="px-5 pt-5 pb-4">
          <DialogHeader className="p-0">
            <DialogTitle className="text-base">Agent connections</DialogTitle>
            <DialogDescription>
              Channels this workspace's agent can send from.
            </DialogDescription>
          </DialogHeader>
        </div>

        <Separator />

        <div className="flex items-start gap-2 border-b border-border/60 bg-muted/40 px-5 py-3 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0 text-amber-500" />
          <p>
            Connect a channel and the agent uses it. Until you do, the agent
            sends from your account connections by default (marked{" "}
            <span className="font-medium text-emerald-600 dark:text-emerald-400">
              default
            </span>
            ).
          </p>
        </div>

        <div className="grid grid-cols-[minmax(7rem,0.6fr)_1.4fr_1.3fr] items-center gap-x-3 px-5 pt-3 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          <span>Channel</span>
          <span>Agent</span>
          <span>Fallback (default)</span>
        </div>

        <div className="px-5 py-2">
          <AnimatePresence initial={false}>
            {ALL_PLATFORMS.map((platform, i) => {
              const fbCons = byPlatform.get(platform) ?? []
              const agentConn = agentCons.find((c) => c.platform === platform) ?? null
              const isConnecting = connecting === platform
              return (
                <motion.div
                  key={platform}
                  initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18, delay: reduceMotion ? 0 : i * 0.03, ease: "easeOut" }}
                >
                  <div className="grid grid-cols-[minmax(7rem,0.6fr)_1.4fr_1.3fr] items-center gap-x-3 py-2.5">
                    <div className="flex min-w-0 items-center gap-2">
                      <PlatformIcon platform={platform} className="size-6" />
                      <span className="truncate text-sm font-medium">
                        {PLATFORM_LABEL[platform]}
                      </span>
                    </div>

                    {/* Agent slot */}
                    {agentConn ? (
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
                        <p className="truncate text-sm font-medium text-emerald-700 dark:text-emerald-300">
                          {agentConn.username}
                        </p>
                        <button
                          type="button"
                          className="shrink-0 cursor-pointer text-xs text-muted-foreground transition-colors hover:text-destructive"
                          onClick={() => disconnect(platform)}
                        >
                          Disconnect
                        </button>
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isConnecting}
                        onClick={() => connect(platform)}
                        className="w-full max-w-40 justify-center border-amber-500/40 text-amber-600 hover:bg-amber-500/10 hover:text-amber-600 dark:text-amber-400 dark:hover:text-amber-400"
                        aria-label={`Connect ${PLATFORM_LABEL[platform]} for the agent`}
                      >
                        {isConnecting && (
                          <RefreshCw className="mr-1.5 size-3.5 animate-spin" />
                        )}
                        {isConnecting ? "Connecting…" : "Set for agent"}
                      </Button>
                    )}

                    {/* Fallback slot */}
                    <div className="min-w-0">
                      {fbCons.length > 0 ? (
                        <p
                          className={cn(
                            "truncate text-sm",
                            agentConn
                              ? "text-muted-foreground/60"
                              : "font-medium text-emerald-600 dark:text-emerald-400",
                          )}
                        >
                          {fbCons.map((c) => c.username).join(", ")}
                          <span
                            className={cn(
                              "ml-1.5 text-[11px] font-normal",
                              agentConn
                                ? "text-muted-foreground/60"
                                : "text-emerald-600/80 dark:text-emerald-400/80",
                            )}
                          >
                            · {agentConn ? "not used" : "default"}
                          </span>
                        </p>
                      ) : (
                        <p className="flex items-center gap-1.5 truncate text-sm text-muted-foreground/70">
                          Not connected
                          <RouterLink
                            to="/accounts"
                            onClick={() => onOpenChange(false)}
                            className="flex shrink-0 items-center gap-0.5 text-amber-500 hover:underline"
                          >
                            <Link className="size-3" />
                            Set up
                          </RouterLink>
                        </p>
                      )}
                    </div>
                  </div>
                  {i < ALL_PLATFORMS.length - 1 && <Separator className="bg-border/50" />}
                </motion.div>
              )
            })}
          </AnimatePresence>
        </div>

        <Separator />

        <div className="flex items-center justify-between px-5 py-4">
          <p className="text-xs text-muted-foreground">
            {agentCons.length} of {ALL_PLATFORMS.length} connected for the agent
          </p>
          <Button
            size="sm"
            onClick={() => onOpenChange(false)}
            className="bg-[#FEA853] text-amber-950 hover:bg-amber-400"
          >
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}