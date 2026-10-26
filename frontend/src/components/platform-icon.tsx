import { cn } from "@/lib/utils"
import { DARK_ICONS, PLATFORM_ICON, PLATFORM_LABEL, type Platform } from "@/lib/platforms"

/** A platform's glyph, on the /accounts board and in a Lace's Messaging. Falls
 * back to the name's first letter when no icon asset exists for the platform. */
export function PlatformIcon({
  platform,
  className,
}: {
  platform: Platform
  className?: string
}) {
  const src = PLATFORM_ICON[platform]
  if (src) return <img src={src} alt="" className={cn("size-8", DARK_ICONS.has(platform) && "dark:invert", className)} />
  return (
    <span
      className={cn(
        "grid size-8 place-items-center rounded-md border border-border bg-muted text-sm font-bold",
        className,
      )}
    >
      {PLATFORM_LABEL[platform].charAt(0)}
    </span>
  )
}
