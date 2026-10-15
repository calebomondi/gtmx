import { cn } from "@/lib/utils"
import { PLATFORM_ICON, type Platform } from "./accounts-type"

/** Platform glyph used by both the /accounts board and the agent
 *  connections dialog. Falls back to a glyph badge when no icon asset
 *  exists for the platform. */
export function PlatformIcon({
  platform,
  className,
}: {
  platform: Platform
  className?: string
}) {
  const src = PLATFORM_ICON[platform]
  if (src) return <img src={src} alt="" className={cn("size-8", className)} />
  return (
    <span
      className={cn(
        "grid size-8 place-items-center rounded-md border border-border bg-muted text-sm font-bold",
        className,
      )}
    >
      X
    </span>
  )
}
