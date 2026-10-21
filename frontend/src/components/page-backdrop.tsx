import { cn } from "@/lib/utils"

import type { BackdropMood, BackdropTone } from "./backdrop-tone"

/** The main area's background: a fine linen weave over the whole page, a
 * soft glow behind the header, and a thin line along the top whose colour is
 * the mood: theme orange when a Lace needs the founder, blue while one works,
 * grey when all are idle. Nothing moves; the colour eases between moods.
 * Chat gets a quieter glow. Decorative and behind everything. */
export function PageBackdrop({ tone, mood }: { tone: BackdropTone; mood: BackdropMood }) {
  return (
    <div aria-hidden data-mood={mood} className="backdrop-mood pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="backdrop-linen absolute inset-0" />
      <div className={cn("backdrop-horizon absolute inset-x-0 top-0 h-80", tone === "calm" && "opacity-50")} />
      <div className="backdrop-mood-line absolute inset-x-0 top-0 h-0.5" />
    </div>
  )
}
