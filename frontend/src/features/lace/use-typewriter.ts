import { useEffect, useRef, useState } from "react"

/** `text` revealed a little at a time, so a reply that arrives in a few
 * bursts still reads as if it is being written. Catches up faster the
 * further behind it is, and stops once it has caught up. */
export function useTypewriter(text: string): string {
  const target = text.length
  const [shown, setShown] = useState(0)
  const position = useRef(0)

  useEffect(() => {
    // Shorter text means the reply started over.
    if (position.current > target) position.current = 0
    let frame = 0
    const tick = () => {
      position.current = Math.min(target, position.current + Math.max(1, Math.ceil((target - position.current) / 12)))
      setShown(position.current)
      if (position.current < target) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target])

  return text.slice(0, Math.min(shown, target))
}
