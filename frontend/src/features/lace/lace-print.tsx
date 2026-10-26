import type { CSSProperties } from "react"
import { motion, useReducedMotion } from "motion/react"

import { Lace } from "@/components/lace-mascot"
import { cn } from "@/lib/utils"

/** A Lace being 3D-printed: the mascot rises layer by layer as `progress`
 * goes from 0 to 1, a nozzle sweeping the layer being laid down and faint
 * layer lines where it is still to come. Its eyes stay heavy until `awake`,
 * then open alert. */
export function LacePrint({ progress, awake, size = 128, className }: {
  progress: number
  awake: boolean
  size?: number
  className?: string
}) {
  const still = useReducedMotion()
  const done = awake || progress >= 1
  // The share still to print, as a top inset: 1 is nothing yet, 0 is whole.
  const unprinted = done ? 0 : 1 - Math.max(0, Math.min(progress, 1))
  return (
    <div
      className={cn("relative", className)}
      style={{ width: size, height: size, "--unprinted": `${unprinted * 100}%` } as CSSProperties}
      role="progressbar"
      aria-label="Building your Lace"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round((1 - unprinted) * 100)}
    >
      {/* The part still to print: its outline and layer lines. */}
      <div
        aria-hidden
        className="absolute inset-0 rounded-[6%] border border-dashed border-theme/40 bg-[repeating-linear-gradient(to_bottom,color-mix(in_oklab,var(--color-theme)_18%,transparent)_0_1px,transparent_1px_7px)]"
      />
      {/* What is printed so far, revealed from the bottom up. */}
      <motion.div
        className="absolute inset-0 transition-[clip-path] duration-700 ease-out [clip-path:inset(var(--unprinted)_0_0_0)]"
        animate={awake && !still ? { scale: [1, 1.08, 1] } : undefined}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <Lace state={awake ? "alert" : "sleepy"} animated={awake} size={size} decorative />
      </motion.div>
      {!done && (
        // The layer being laid: a hot line across, and the nozzle sweeping it.
        <div aria-hidden className="absolute -inset-x-[8%] top-(--unprinted) h-0.5 transition-[top] duration-700 ease-out">
          <div className="h-full bg-theme/70 shadow-[0_0_8px_var(--color-theme)]" />
          <motion.div
            className="absolute -top-1.5 h-2.5 w-3 rounded-[2px] bg-theme shadow-[0_0_12px_var(--color-theme)]"
            initial={{ left: "0%" }}
            animate={still ? undefined : { left: ["0%", "calc(100% - 0.75rem)"] }}
            transition={{ duration: 1.1, ease: "easeInOut", repeat: Infinity, repeatType: "reverse" }}
          />
        </div>
      )}
    </div>
  )
}
