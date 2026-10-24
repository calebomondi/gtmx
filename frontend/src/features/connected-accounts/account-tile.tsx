import { motion, useReducedMotion } from "motion/react"

import { PlatformIcon } from "@/components/platform-icon"
import { COMING_SOON, PLATFORM_LABEL, type Platform } from "@/lib/platforms"
import { cn } from "@/lib/utils"

import type { Connection } from "./accounts-type"

/** One app on the Accounts board: connected (and how it's doing), or ready to connect. */
export type GridItem =
  | { kind: "connection"; connection: Connection }
  | { kind: "available"; platform: Platform; ready: boolean }

export function AccountTile({
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
      
      {COMING_SOON.has(platform) && (
        <span className="absolute top-2 right-2 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
              title="Connect it now; your Lace starts using it as its skills for it arrive.">
          Soon
        </span>
      )}
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
            <>
                <p className="truncate text-center text-xs font-medium">{PLATFORM_LABEL[platform]}</p>
                <p className="text-center text-xs text-muted-foreground transition-colors group-hover:text-[#FEA853]">
                    {item.kind === "available" && !item.ready ? "Setup required" : "Connect"}
                </p>
            </>
            )}
        </div>
      </div>

    </motion.article>
  )
}
