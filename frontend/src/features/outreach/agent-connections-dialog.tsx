"use client"

import * as React from "react"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import { Info, Link } from "lucide-react"
import { Link as RouterLink } from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { PlatformIcon } from "@/features/connected-accounts/platform-icon"
import {
  ALL_PLATFORMS,
  PLATFORM_LABEL,
  fetchConnections,
  type Connection,
  type Platform,
} from "@/features/connected-accounts/accounts-type"

/**
 * Which channels outreach can send through. Outreach sends as YOU, through the
 * accounts you connected on /accounts -- always after your approval.
 */
export function AgentConnectionsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const reduceMotion = useReducedMotion()
  const [connections, setConnections] = React.useState<Connection[] | null>(null)

  React.useEffect(() => {
    if (!open) return
    let cancelled = false
    fetchConnections()
      .then((rows) => !cancelled && setConnections(rows))
      .catch(() => !cancelled && setConnections([]))
    return () => {
      cancelled = true
    }
  }, [open])

  const liveByPlatform = React.useMemo(() => {
    const map = new Map<Platform, Connection[]>()
    for (const c of connections ?? []) {
      if (c.status !== "live") continue
      map.set(c.platform, [...(map.get(c.platform) ?? []), c])
    }
    return map
  }, [connections])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md p-0">
        <div className="px-5 pt-5 pb-4">
          <DialogHeader className="p-0">
            <DialogTitle className="text-base">Outreach channels</DialogTitle>
            <DialogDescription>Where outreach can send from.</DialogDescription>
          </DialogHeader>
        </div>

        <Separator />

        <div className="flex items-start gap-2 border-b border-border/60 bg-muted/40 px-5 py-3 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0 text-amber-500" />
          <p>
            Outreach sends as you, through the accounts you connected — and only
            after you approve each message.
          </p>
        </div>

        <div className="px-5 py-2">
          <AnimatePresence initial={false}>
            {ALL_PLATFORMS.map((platform, i) => {
              const live = liveByPlatform.get(platform) ?? []
              return (
                <motion.div
                  key={platform}
                  initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18, delay: reduceMotion ? 0 : i * 0.03, ease: "easeOut" }}
                >
                  <div className="flex items-center justify-between gap-3 py-2.5">
                    <div className="flex min-w-0 items-center gap-2">
                      <PlatformIcon platform={platform} className="size-6" />
                      <span className="truncate text-sm font-medium">{PLATFORM_LABEL[platform]}</span>
                    </div>
                    {connections === null ? (
                      <span className="text-sm text-muted-foreground">…</span>
                    ) : live.length > 0 ? (
                      <p className="flex min-w-0 items-center gap-2 text-sm font-medium text-emerald-600 dark:text-emerald-400">
                        <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
                        <span className="truncate">{live.map((c) => c.username).join(", ")}</span>
                      </p>
                    ) : (
                      <p className="flex items-center gap-1.5 text-sm text-muted-foreground/70">
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
                  {i < ALL_PLATFORMS.length - 1 && <Separator className="bg-border/50" />}
                </motion.div>
              )
            })}
          </AnimatePresence>
        </div>

        <Separator />

        <div className="flex items-center justify-between px-5 py-4">
          <p className="text-xs text-muted-foreground">
            {liveByPlatform.size} of {ALL_PLATFORMS.length} channels connected
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
