import { cn } from "@/lib/utils"

/** The Lace's face in the chat. A plain mark for now; the animated mascot
 * slots in here, with `working` mapping to its "thinking" state. */
export function LaceAvatar({ working = false, className }: { working?: boolean; className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("flex size-8 shrink-0 items-center justify-center gap-1 rounded-sm bg-theme", working && "animate-pulse", className)}
    >
      <span className="size-1.5 rounded-[1px] bg-neutral-900" />
      <span className="size-1.5 rounded-[1px] bg-neutral-900" />
    </div>
  )
}
