import { useEffect, useRef, type RefObject } from 'react'

import { prefersStill } from '../lib/motion'

/** Spacing of the field of squares, and each square's resting size, in CSS px. */
const PITCH = { wide: 22, narrow: 26 }
const DOT = 3
/** A ping leaves Lace this often, travels this fast, and is this wide. */
const PING_EVERY_MS = 3400
const PING_SPEED = 300
const PING_BAND = 64
/** How far the pointer's lens reaches, and how much it lifts a square. */
const LENS_PX = 130
const LENS_GROW = 3.2
/** A find shows this long, and the next is kept this far from what's on the page. */
const FIND_SHOW_MS = 2600
const FIND_FADE_MS = 500
const KEEP_CLEAR_PX = 14
/** How far a find on show warms the squares around it. */
const GLOW_PX = 110
const FONT = '600 12px "Funnel Sans Variable", ui-sans-serif, system-ui, sans-serif'

// What a ping turns up, from anywhere in the world.
const FINDS = [
  'A tender in Nairobi', 'A partner in Lagos', 'A grant, closing in 9 days', 'A CTO in Kigali to reach',
  'An accelerator with an open call', 'A competitor changed its pricing', 'Founders Summit, Berlin',
  'Head of Ops in São Paulo, hiring', 'A pilot customer in Cape Town', 'A pre-seed investor in Jakarta',
  'A tender in Accra', 'A partner in Austin',
]

interface Ping { born: number; find: Find | null }
interface Find { x: number; y: number; at: number; text: string; shown: number | null }

function color(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
}

/** The hero's backdrop: a field of Lace's own rounded squares, like halftone
 * on paper. Every few seconds a ping leaves the Lace in the headline and
 * ripples out, lifting and warming the squares it passes; where it lands, a
 * find surfaces for a moment (a tender, a partner, a lead) and sinks back.
 * The pointer is a lens that lifts the squares under it. Draws only while
 * the hero is on screen; with reduced motion, one still frame. */
export function HeroRadar({ hero, origin, copy, demo }: {
  hero: RefObject<HTMLElement | null>
  /** Where pings start: Lace in the headline. */
  origin: RefObject<HTMLElement | null>
  /** What finds must not land on: the headline column and the demo. */
  copy: RefObject<HTMLElement | null>
  demo: RefObject<HTMLElement | null>
}) {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const area = hero.current
    const el = canvas.current
    const ctx = el?.getContext('2d')
    if (!area || !el || !ctx) return
    const ink = color('--color-ink', '#121212')
    const brand = color('--color-brand', '#fea853')
    const panel = color('--color-panel', '#ffffff')
    const still = prefersStill()

    let width = 0
    let height = 0
    let pitch = PITCH.wide
    let from = { x: 0, y: 0 }
    let blocked: DOMRect[] = []
    // The copy column, where the field stays faint so the words read cleanly.
    let quiet: DOMRect | null = null
    const measure = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const box = area.getBoundingClientRect()
      width = box.width
      height = box.height
      el.width = Math.round(width * dpr)
      el.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      pitch = width < 640 ? PITCH.narrow : PITCH.wide
      const lace = origin.current?.getBoundingClientRect()
      from = lace ? { x: lace.left + lace.width / 2 - box.left, y: lace.top + lace.height / 2 - box.top }
                  : { x: width * 0.25, y: height * 0.35 }
      ctx.font = FONT
      const words = copy.current?.getBoundingClientRect()
      quiet = words ? new DOMRect(words.left - box.left, words.top - box.top, words.width, words.height) : null
      blocked = [copy, demo].flatMap((ref) => {
        const r = ref.current?.getBoundingClientRect()
        return r ? [new DOMRect(r.left - box.left - KEEP_CLEAR_PX, r.top - box.top - KEEP_CLEAR_PX,
                                r.width + 2 * KEEP_CLEAR_PX, r.height + 2 * KEEP_CLEAR_PX)] : []
      })
    }

    const labelSize = (text: string) => ({ w: ctx.measureText(text).width + 28, h: 24 })
    const clear = (x: number, y: number, w: number, h: number) =>
      x > 8 && y > 8 && x + w < width - 8 && y + h < height - 8 &&
      blocked.every((b) => x + w < b.left || x > b.right || y + h < b.top || y > b.bottom)

    let nextFind = Math.floor(Math.random() * FINDS.length)
    /** Somewhere open on the page for the next find, and when the ping reaches it. */
    const placeFind = (born: number): Find | null => {
      const text = FINDS[nextFind % FINDS.length]
      const { w, h } = labelSize(text)
      for (let tries = 0; tries < 24; tries++) {
        const x = Math.random() * (width - w)
        const y = Math.random() * (height - h)
        if (!clear(x, y, w, h)) continue
        nextFind++
        const reach = Math.hypot(x + 6 - from.x, y + h / 2 - from.y)
        return { x, y, at: born + (reach / PING_SPEED) * 1000, text, shown: null }
      }
      return null
    }

    let pointer: { x: number; y: number } | null = null
    let pings: Ping[] = []
    let lastPing = -Infinity

    const draw = (ms: number) => {
      ctx.clearRect(0, 0, width, height)
      if (ms - lastPing > PING_EVERY_MS) {
        lastPing = ms
        pings.push({ born: ms, find: placeFind(ms) })
      }
      const reachMax = Math.hypot(Math.max(from.x, width - from.x), Math.max(from.y, height - from.y))
      pings = pings.filter((p) => ((ms - p.born) / 1000) * PING_SPEED < reachMax + PING_BAND
        || (p.find && p.find.shown !== null && ms - p.find.shown < FIND_SHOW_MS))
      const rings = pings.map((p) => ((ms - p.born) / 1000) * PING_SPEED)
      // Finds on show warm the squares around them.
      const glows = pings.flatMap((p) => {
        const f = p.find
        if (!f || f.shown === null || ms - f.shown > FIND_SHOW_MS) return []
        const age = ms - f.shown
        return [{ x: f.x + labelSize(f.text).w / 2, y: f.y + 12,
                  k: Math.min(1, age / FIND_FADE_MS, (FIND_SHOW_MS - age) / FIND_FADE_MS) }]
      })

      for (let y = pitch / 2; y < height; y += pitch) {
        for (let x = pitch / 2; x < width; x += pitch) {
          const d = Math.hypot(x - from.x, y - from.y)
          let lift = 0
          for (const r of rings) {
            const off = (d - r) / PING_BAND
            lift = Math.max(lift, Math.exp(-off * off * 4) * Math.sqrt(Math.max(0, 1 - r / reachMax)))
          }
          for (const g of glows) {
            lift = Math.max(lift, g.k * Math.max(0, 1 - Math.hypot(x - g.x, y - g.y) / GLOW_PX) * 0.8)
          }
          const hushed = quiet !== null && x > quiet.left && x < quiet.right && y > quiet.top && y < quiet.bottom
          if (hushed) lift *= 0.45
          let size = DOT + lift * 5
          let px = x
          let py = y
          if (pointer) {
            const near = Math.max(0, 1 - Math.hypot(x - pointer.x, y - pointer.y) / LENS_PX)
            size += near * near * LENS_GROW
            px += (pointer.x - x) * near * 0.08
            py += (pointer.y - y) * near * 0.08
          }
          ctx.globalAlpha = (hushed ? 0.04 : 0.1) + lift * 0.75
          ctx.fillStyle = lift > 0.08 ? brand : ink
          roundRect(ctx, px - size / 2, py - size / 2, size, size, size * 0.3)
          ctx.fill()
        }
      }

      for (const ping of pings) {
        const find = ping.find
        if (!find || ms < find.at) continue
        find.shown ??= ms
        const age = ms - find.shown
        if (age > FIND_SHOW_MS) continue
        const fade = Math.min(1, age / FIND_FADE_MS, (FIND_SHOW_MS - age) / FIND_FADE_MS)
        const { w, h } = labelSize(find.text)
        const rise = (1 - fade) * 6
        ctx.globalAlpha = fade
        ctx.fillStyle = panel
        roundRect(ctx, find.x, find.y + rise, w, h, 6)
        ctx.fill()
        ctx.strokeStyle = ink
        ctx.lineWidth = 1.5
        ctx.stroke()
        ctx.fillStyle = brand
        roundRect(ctx, find.x + 9, find.y + rise + h / 2 - 4, 8, 8, 2.4)
        ctx.fill()
        ctx.fillStyle = ink
        ctx.textBaseline = 'middle'
        ctx.fillText(find.text, find.x + 22, find.y + rise + h / 2 + 0.5)
      }
      ctx.globalAlpha = 1
    }

    measure()
    if (still) {
      draw(0)
      return
    }

    let frame = 0
    const tick = (ms: number) => {
      draw(ms)
      frame = requestAnimationFrame(tick)
    }
    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse') return
      const box = area.getBoundingClientRect()
      pointer = { x: event.clientX - box.left, y: event.clientY - box.top }
    }
    const onLeave = () => { pointer = null }
    const resized = new ResizeObserver(measure)
    const watcher = new IntersectionObserver(([entry]) => {
      cancelAnimationFrame(frame)
      if (entry.isIntersecting) frame = requestAnimationFrame(tick)
    })
    resized.observe(area)
    // Webfonts reflow the headline, which moves Lace.
    void document.fonts?.ready.then(measure)
    watcher.observe(area)
    area.addEventListener('pointermove', onMove)
    area.addEventListener('pointerleave', onLeave)
    return () => {
      cancelAnimationFrame(frame)
      resized.disconnect()
      watcher.disconnect()
      area.removeEventListener('pointermove', onMove)
      area.removeEventListener('pointerleave', onLeave)
    }
  }, [hero, origin, copy, demo])

  return <canvas ref={canvas} aria-hidden className="pointer-events-none absolute inset-0 -z-10 size-full" />
}
