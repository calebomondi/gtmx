import { cn } from "@/lib/utils"

import type { BackdropTone } from "./backdrop-tone"

// Each thread is one period of a wave (800 units) drawn twice, so sliding the
// 200%-wide layer left by half loops without a seam. They cross each other,
// and drift at different speeds and directions, to read as woven.
const THREADS = [
  { d: "M0 120 C200 40 600 200 800 120 S1400 40 1600 120", opacity: 0.4, drift: "animate-thread-drift-slow" },
  { d: "M0 170 C250 250 550 90 800 170 S1350 250 1600 170", opacity: 0.28, drift: "animate-thread-drift-reverse" },
  { d: "M0 70 C300 130 500 10 800 70 S1300 130 1600 70", opacity: 0.2, drift: "animate-thread-drift-slower" },
] as const

/** The main area's background: a warm wash, a faint dot grid and orange
 * threads drifting across the top, fading out down the page. Decorative,
 * behind everything, and still when the OS asks for reduced motion. */
export function PageBackdrop({ tone }: { tone: BackdropTone }) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className="backdrop-wash absolute inset-0" />
      {tone === "full" && <div className="backdrop-dots absolute inset-0" />}
      <div className={cn("backdrop-threads absolute inset-x-0 top-0 h-80", tone === "calm" && "opacity-40")}>
        {THREADS.map((thread) => (
          <svg key={thread.d} viewBox="0 0 1600 320" preserveAspectRatio="none"
               className={cn("absolute inset-y-0 left-0 h-full w-[200%] motion-reduce:animate-none", thread.drift)}>
            <path d={thread.d} fill="none" strokeWidth={1.5} strokeLinecap="round" vectorEffect="non-scaling-stroke"
                  className="stroke-theme" strokeOpacity={thread.opacity} />
          </svg>
        ))}
      </div>
    </div>
  )
}
