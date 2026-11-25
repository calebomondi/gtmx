import type { ReactNode } from "react"
import { cn } from "@/lib/cn"
import { useParallax } from "@/lib/hooks"

type Props = {
  children: ReactNode
  speed?: number
  className?: string
}

/** Lets display type drift against the imagery as the page moves. */
export function Parallax({ children, speed = 0.05, className }: Props) {
  const ref = useParallax(speed)
  return (
    <div ref={ref} className={cn("will-change-transform", className)}>
      {children}
    </div>
  )
}
