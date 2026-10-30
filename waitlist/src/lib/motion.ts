import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'

/** A replay this soon after the last start is ignored, so moving the pointer
 * around a scene doesn't restart it over and over. */
const REPLAY_GAP_MS = 2500

export function prefersStill(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export interface Play {
  /** Bumps on every start: key the scene on it, so each start remounts it from its first frame. */
  run: number
  /** Show only the last frame: before the first start, and always with reduced motion. */
  still: boolean
  replay: () => void
}

/** A scene that plays once when `el` first comes into view, and again when
 * asked (a hover or a tap). With reduced motion it never plays. */
export function usePlay(el: RefObject<HTMLElement | null>): Play {
  const [reduced] = useState(prefersStill)
  const [run, setRun] = useState(0)
  const startedAt = useRef(0)

  const start = useCallback(() => {
    if (reduced || Date.now() - startedAt.current < REPLAY_GAP_MS) return
    startedAt.current = Date.now()
    setRun((n) => n + 1)
  }, [reduced])

  useEffect(() => {
    const node = el.current
    if (!node || reduced) return
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      start()
      observer.disconnect()
    }, { threshold: 0.5 })
    observer.observe(node)
    return () => observer.disconnect()
  }, [el, reduced, start])

  return { run, still: reduced || run === 0, replay: start }
}
