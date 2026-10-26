import { cn } from "@/lib/utils"

/** How many replies are new. */
export function UnreadBadge({ count, className }: { count: number; className?: string }) {
  return (
    <span aria-label={`${count} new ${count === 1 ? "reply" : "replies"}`}
          className={cn("grid min-w-4 place-items-center rounded-full bg-theme px-1 text-[10px] leading-4 font-medium text-neutral-900", className)}>
      {count}
    </span>
  )
}
