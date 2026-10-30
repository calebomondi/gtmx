import { useEffect, useRef, type RefObject } from 'react'

import { prefersStill } from '../lib/motion'

/** How quickly the glow catches up with where it's headed: about a second behind. */
const FOLLOW_RATE = 1.6
/** After this long without the pointer moving, the glow drifts on its own. */
const IDLE_MS = 2500
/** Where it rests, and drifts around, as a share of the hero: the top right. */
const REST = { x: 0.82, y: 0.22 }
const DRIFT = { x: 0.12, y: 0.16 }

/** The hero's warm glow. It trails the pointer around the hero, about a
 * second behind; left alone (or on a phone) it drifts slowly around the top
 * right. Moves only while the hero is on screen; with reduced motion it stays
 * at rest. Placed by transform, outside React's render. */
export function HeroGlow({ hero }: { hero: RefObject<HTMLElement | null> }) {
  const glow = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const area = hero.current
    const el = glow.current
    if (!area || !el) return
    const place = (x: number, y: number) => {
      el.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`
    }
    const rest = () => ({ x: area.clientWidth * REST.x, y: area.clientHeight * REST.y })
    let at = rest()
    place(at.x, at.y)
    if (prefersStill()) return

    let pointer: { x: number; y: number; moved: number } | null = null
    let frame = 0
    let last = 0

    const tick = (ms: number) => {
      const dt = last ? Math.min(0.1, (ms - last) / 1000) : 0
      last = ms
      const w = area.clientWidth
      const h = area.clientHeight
      const target = pointer && ms - pointer.moved < IDLE_MS
        ? pointer
        : {
            x: w * (REST.x + DRIFT.x * Math.sin(ms / 6400)),
            y: h * (REST.y + DRIFT.y * Math.sin(ms / 9100)),
          }
      const k = 1 - Math.exp(-dt * FOLLOW_RATE)
      at = { x: at.x + (target.x - at.x) * k, y: at.y + (target.y - at.y) * k }
      place(at.x, at.y)
      frame = requestAnimationFrame(tick)
    }

    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse') return
      const box = area.getBoundingClientRect()
      pointer = { x: event.clientX - box.left, y: event.clientY - box.top, moved: performance.now() }
    }
    const watcher = new IntersectionObserver(([entry]) => {
      cancelAnimationFrame(frame)
      last = 0
      if (entry.isIntersecting) frame = requestAnimationFrame(tick)
    })
    watcher.observe(area)
    area.addEventListener('pointermove', onMove)
    return () => {
      cancelAnimationFrame(frame)
      watcher.disconnect()
      area.removeEventListener('pointermove', onMove)
    }
  }, [hero])

  return (
    <div ref={glow} aria-hidden
         className="hero-glow pointer-events-none absolute top-0 left-0 -z-10 h-[30rem] w-[60rem] max-w-[160vw] will-change-transform" />
  )
}
