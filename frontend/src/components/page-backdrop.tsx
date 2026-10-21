import { cn } from "@/lib/utils"

import type { BackdropTone } from "./backdrop-tone"

// The band a thread is drawn in, in viewBox units; its wave swings around the middle.
const BAND = { width: 1600, height: 200 }
const DRIFT = {
  slow: "animate-thread-drift-slow",
  slower: "animate-thread-drift-slower",
  reverse: "animate-thread-drift-reverse",
} as const

/** One period of a wave (800 units) drawn twice, so sliding the 200%-wide
 * layer left by half loops without a seam. A negative `swing` starts low. */
function wave(swing: number): string {
  const mid = BAND.height / 2
  return `M0 ${mid} C200 ${mid - swing} 600 ${mid + swing} 800 ${mid} S1400 ${mid - swing} 1600 ${mid}`
}

// Spread down the whole page, crossing in pairs, each at its own pace and
// direction, faintest mid-page where most reading happens.
const THREADS = [
  { at: "top-[4%]", swing: 70, opacity: 0.38, width: 1.5, drift: DRIFT.slow },
  { at: "top-[18%]", swing: -50, opacity: 0.24, width: 1.25, drift: DRIFT.reverse },
  { at: "top-[36%]", swing: 85, opacity: 0.14, width: 1, drift: DRIFT.slower },
  { at: "top-[54%]", swing: -60, opacity: 0.16, width: 1.25, drift: DRIFT.slow },
  { at: "top-[71%]", swing: 75, opacity: 0.2, width: 1, drift: DRIFT.reverse },
  { at: "top-[87%]", swing: -45, opacity: 0.3, width: 1.5, drift: DRIFT.slower },
] as const
// In chat only the top threads show, fainter.
const CALM_THREADS = 2

// The lacing: eyelet rows down both sides, and a cross between each pair of
// rows, as on a laced shoe. In viewBox percent.
const EYELET_ROWS = 9
const LACES = Array.from({ length: EYELET_ROWS - 1 }, (_, i) => {
  const y1 = (i * 100) / (EYELET_ROWS - 1)
  const y2 = ((i + 1) * 100) / (EYELET_ROWS - 1)
  return `M0 ${y1} L100 ${y2} M100 ${y1} L0 ${y2}`
}).join(" ")

function Thread({ thread }: { thread: (typeof THREADS)[number] }) {
  return (
    <div className={cn("absolute inset-x-0 h-44 -translate-y-1/2", thread.at)}>
      <svg viewBox={`0 0 ${BAND.width} ${BAND.height}`} preserveAspectRatio="none"
           className={cn("absolute inset-y-0 left-0 h-full w-[200%] will-change-transform motion-reduce:animate-none",
                         thread.drift)}>
        <path d={wave(thread.swing)} fill="none" strokeWidth={thread.width} strokeLinecap="round"
              vectorEffect="non-scaling-stroke" className="stroke-theme" strokeOpacity={thread.opacity} />
      </svg>
    </div>
  )
}

/** The main area's background, over the whole page: soft drifting glows in
 * the theme colours, threads woven across from top to bottom, a faint lacing
 * between eyelets down both sides, a dot grid that fades behind the content,
 * and a fine grain against banding. Chat gets a quieter version. Decorative,
 * behind everything, and still when the OS asks for reduced motion. */
export function PageBackdrop({ tone }: { tone: BackdropTone }) {
  const full = tone === "full"
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div className={cn("absolute inset-0", !full && "opacity-50")}>
        <div className="backdrop-glow backdrop-glow-theme" />
        <div className="backdrop-glow backdrop-glow-rose" />
        <div className="backdrop-glow backdrop-glow-amber" />
      </div>
      {full && (
        <>
          <div className="backdrop-dots absolute inset-0" />
          <div className="backdrop-lacing absolute inset-y-6 inset-x-3">
            <div className="backdrop-eyelets absolute inset-y-0 left-0 w-3" />
            <div className="backdrop-eyelets absolute inset-y-0 right-0 w-3" />
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-x-1.5 inset-y-1.5 size-[calc(100%-0.75rem)]">
              <path d={LACES} fill="none" strokeWidth={1} vectorEffect="non-scaling-stroke" className="stroke-theme"
                    strokeOpacity={0.1} />
            </svg>
          </div>
        </>
      )}
      <div className={cn("absolute inset-0", !full && "opacity-40")}>
        {(full ? THREADS : THREADS.slice(0, CALM_THREADS)).map((thread) => <Thread key={thread.at} thread={thread} />)}
      </div>
      <div className="backdrop-grain absolute inset-0" />
    </div>
  )
}
