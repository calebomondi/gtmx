import { useEffect, useRef } from 'react'

import { prefersStill } from '../lib/motion'

/** The field's spacing, each square's size, and how strong it is: far
 * fainter than the hero's own field (hero-radar.tsx). */
const PITCH = { wide: 28, narrow: 34 }
const DOT = 3
const ALPHA = 0.06
/** Behind a section's heading and content the squares fall to this share. */
const HUSHED = 0.3
/** How far the hush reaches past the content's edge, fading out. */
const FEATHER_PX = 48
/** The warm light: its radius as a share of the screen's width, and strength. */
const GLOW_RADIUS = 0.55
const GLOW_ALPHA = 0.07
/** Where the light sits on the screen (shares of width and height), section
 * by section, in turn: across the top right, then low on the left, and on. */
const GLOW_AT = [
  { x: 0.82, y: 0.25 },
  { x: 0.16, y: 0.72 },
  { x: 0.78, y: 0.7 },
  { x: 0.2, y: 0.28 },
]

function color(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

/** How much a square at (x, y) is hushed by the content near it: 1 far from
 * it, HUSHED inside it, fading over FEATHER_PX between. */
function openness(x: number, y: number, quiet: DOMRect[]): number {
  let open = 1
  for (const r of quiet) {
    const dx = Math.max(r.left - x, 0, x - r.right)
    const dy = Math.max(r.top - y, 0, y - r.bottom)
    const d = Math.hypot(dx, dy)
    if (d < FEATHER_PX) open = Math.min(open, HUSHED + (1 - HUSHED) * (d / FEATHER_PX))
  }
  return open
}

/** The page's paper below the hero: a faint field of Lace's rounded squares,
 * fixed to the screen so the page glides over it, hushed behind each
 * section's words, and one soft warm light that moves from side to side as
 * the sections pass. Drawn when the page scrolls or resizes, never on a
 * loop; with reduced motion the light stays in one place. */
export function PageBackdrop() {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const el = canvas.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return
    const ink = color('--color-ink', '#17150f')
    const still = prefersStill()
    let width = 0
    let height = 0
    let frame = 0

    const size = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = window.innerWidth
      height = window.innerHeight
      el.width = Math.round(width * dpr)
      el.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    /** Where the light is now: between the places of the sections either
     * side of the screen's middle, by how far the page is through them. */
    const glowAt = (sections: HTMLElement[]) => {
      if (still || !sections.length) return GLOW_AT[0]
      const mid = height / 2
      let i = sections.findIndex((s) => s.getBoundingClientRect().bottom > mid)
      if (i < 0) i = sections.length - 1
      const box = sections[i].getBoundingClientRect()
      const t = Math.min(1, Math.max(0, (mid - box.top) / Math.max(1, box.height)))
      const a = GLOW_AT[i % GLOW_AT.length]
      const b = GLOW_AT[(i + 1) % GLOW_AT.length]
      const k = t * t * (3 - 2 * t)
      return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k }
    }

    const draw = () => {
      frame = 0
      ctx.clearRect(0, 0, width, height)
      const sections = [...document.querySelectorAll<HTMLElement>('main > section')]
      const glow = glowAt(sections)
      const light = ctx.createRadialGradient(glow.x * width, glow.y * height, 0, glow.x * width, glow.y * height,
                                             GLOW_RADIUS * Math.max(width, height))
      light.addColorStop(0, `rgb(254 168 83 / ${GLOW_ALPHA})`)
      light.addColorStop(1, 'rgb(254 168 83 / 0)')
      ctx.fillStyle = light
      ctx.fillRect(0, 0, width, height)

      const quiet = [...document.querySelectorAll('[data-quiet]')]
        .map((q) => q.getBoundingClientRect())
        .filter((r) => r.bottom > -FEATHER_PX && r.top < height + FEATHER_PX)
      const pitch = width < 640 ? PITCH.narrow : PITCH.wide
      ctx.fillStyle = ink
      for (let y = pitch / 2; y < height; y += pitch) {
        for (let x = pitch / 2; x < width; x += pitch) {
          ctx.globalAlpha = ALPHA * openness(x, y, quiet)
          ctx.beginPath()
          ctx.roundRect(x - DOT / 2, y - DOT / 2, DOT, DOT, DOT * 0.3)
          ctx.fill()
        }
      }
      ctx.globalAlpha = 1
    }

    const schedule = () => { frame ||= requestAnimationFrame(draw) }
    const onResize = () => {
      size()
      schedule()
    }
    size()
    draw()
    // Webfonts and the pilot count settle the layout after the first paint.
    void document.fonts?.ready.then(schedule)
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return <canvas ref={canvas} aria-hidden className="pointer-events-none fixed inset-0 -z-10 size-full" />
}
