import { useEffect, useRef, useState } from 'react'

import { prefersStill } from '../lib/motion'

import { CELL_DEGREES, WORLD_GRID } from './world-grid'

// The theme's colours (index.css), for the canvas, which can't read classes.
const BRAND = '254, 168, 83'
const BRAND_DEEP = '240, 138, 36'
const INK = '18, 18, 18'
const HIGHLIGHT = '255, 225, 187'

/** Seconds per turn, and how far the north pole leans towards the viewer. */
const TURN_S = 40
const TILT = (18 * Math.PI) / 180
/** The still view (reduced motion), and where the turn starts: the Atlantic. */
const START_LON = -20
/** A find: how often one appears, and how long it shows. */
const FIND_EVERY_S = 1.3
const FIND_LIFE_S = 3.6
/** Turning to a place someone named: how quickly, and how long it stays there with its pin. */
const AIM_RATE = 2.4
const AIM_HOLD_S = 4

const RAD = Math.PI / 180

interface Cell {
  lat: number
  lon: number
}

const LAND: Cell[] = WORLD_GRID.flatMap((row, r) =>
  [...row].flatMap((ch, c) => (ch === '#'
    ? [{ lat: (90 - CELL_DEGREES / 2 - r * CELL_DEGREES) * RAD, lon: (-180 + CELL_DEGREES / 2 + c * CELL_DEGREES) * RAD }]
    : [])),
)

// The sea: a sparser grid of dots over the whole sphere.
const SEA: Cell[] = []
for (let lat = -70; lat <= 70; lat += 10) {
  for (let lon = -180; lon < 180; lon += 10) SEA.push({ lat: lat * RAD, lon: lon * RAD })
}

/** Where a cell lands on screen when the globe faces `center` (radians):
 * x and y in -1..1, and z, its depth (above 0 is the near side). */
function project(cell: Cell, center: number) {
  const d = cell.lon - center
  const cosLat = Math.cos(cell.lat)
  return {
    x: cosLat * Math.sin(d),
    y: Math.cos(TILT) * Math.sin(cell.lat) - Math.sin(TILT) * cosLat * Math.cos(d),
    z: Math.sin(TILT) * Math.sin(cell.lat) + Math.cos(TILT) * cosLat * Math.cos(d),
  }
}

/** A place to turn to, in degrees, with the name pinned on it. */
export interface Place {
  name: string
  lat: number
  lon: number
}

interface Find {
  cell: Cell
  born: number
  /** Seconds it shows; a named place's pin stays while the globe holds on it. */
  life: number
  label?: string
}

/** The shortest signed turn from `from` to `to`, in radians. */
function turn(from: number, to: number): number {
  return Math.atan2(Math.sin(to - from), Math.cos(to - from))
}

function draw(ctx: CanvasRenderingContext2D, size: number, center: number, finds: Find[], now: number) {
  const r = size * 0.46
  const cx = size / 2
  const cy = size / 2
  ctx.clearRect(0, 0, size, size)

  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.fillStyle = `rgba(${HIGHLIGHT}, 0.45)`
  ctx.fill()
  ctx.lineWidth = 1.2
  ctx.strokeStyle = `rgba(${BRAND_DEEP}, 0.55)`
  ctx.stroke()

  for (const cell of SEA) {
    const p = project(cell, center)
    if (p.z <= 0) continue
    ctx.fillStyle = `rgba(${INK}, ${0.05 + 0.1 * p.z})`
    ctx.fillRect(cx + p.x * r - 1, cy - p.y * r - 1, 2, 2)
  }

  // A cell's side on screen: its width on the sphere, shrinking towards the
  // edge so the boxes read as a round globe.
  const cellSide = r * CELL_DEGREES * RAD
  for (const cell of LAND) {
    const p = project(cell, center)
    if (p.z <= 0) continue
    const side = cellSide * (0.42 + 0.48 * p.z)
    ctx.fillStyle = `rgba(${p.z > 0.55 ? BRAND : BRAND_DEEP}, ${0.35 + 0.65 * p.z})`
    ctx.fillRect(cx + p.x * r - side / 2, cy - p.y * r - side / 2, side, side)
  }

  for (const find of finds) {
    const p = project(find.cell, center)
    if (p.z <= 0) continue
    const age = (now - find.born) / find.life
    const side = cellSide * (0.5 + 0.5 * p.z)
    const x = cx + p.x * r
    const y = cy - p.y * r
    ctx.strokeStyle = `rgba(${BRAND_DEEP}, ${0.8 * (1 - age)})`
    ctx.lineWidth = 2
    const ring = side * (1 + 2.2 * age)
    ctx.strokeRect(x - ring / 2, y - ring / 2, ring, ring)
    ctx.fillStyle = `rgba(${INK}, ${age < 0.85 ? 1 : (1 - age) / 0.15})`
    ctx.fillRect(x - side / 2, y - side / 2, side, side)
    if (find.label) {
      ctx.font = '600 13px "Geist Variable", system-ui, sans-serif'
      ctx.fillStyle = `rgba(${INK}, ${age < 0.85 ? 1 : (1 - age) / 0.15})`
      ctx.fillText(find.label, x + side, y - side)
    }
  }
}

/** The world as square boxes on a slowly turning globe, with finds lighting
 * up on land as it turns. Given a `place`, it turns there, pins it, holds a
 * moment, and turns on. Turns only on screen; still with reduced motion,
 * where it simply faces the place. */
export function RotatingGlobe({ place = null }: { place?: Place | null }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [still] = useState(prefersStill)
  // Read by the drawing loop, which outlives renders.
  const aim = useRef<{ place: Place; pinned: boolean; until: number } | null>(null)
  const show = useRef<(place: Place) => void>(() => {})

  useEffect(() => {
    if (place) show.current(place)
  }, [place])

  useEffect(() => {
    const el = canvas.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return
    let size = 0
    let center = START_LON * RAD
    let visible = false
    let frame = 0
    let last = 0
    let nextFind = 0
    let finds: Find[] = []

    show.current = (target) => {
      if (still) {
        center = target.lon * RAD
        finds = [{ cell: { lat: target.lat * RAD, lon: target.lon * RAD }, born: 0, life: Infinity, label: target.name }]
        draw(ctx, size, center, finds, 0)
        return
      }
      aim.current = { place: target, pinned: false, until: Infinity }
    }

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      size = el.clientWidth
      el.width = Math.round(size * dpr)
      el.height = Math.round(size * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      draw(ctx, size, center, finds, last)
    }

    const tick = (ms: number) => {
      const now = ms / 1000
      const dt = last ? now - last : 0
      last = now
      const target = aim.current
      if (target && now < target.until) {
        // Turning to the named place, easing in; pinned once it faces us.
        const lon = target.place.lon * RAD
        const left = turn(center, lon)
        center += left * (1 - Math.exp(-dt * AIM_RATE))
        if (!target.pinned && Math.abs(left) < 0.05) {
          target.pinned = true
          target.until = now + AIM_HOLD_S
          finds.push({ cell: { lat: target.place.lat * RAD, lon }, born: now, life: AIM_HOLD_S, label: target.place.name })
        }
      } else {
        if (target) aim.current = null
        // West to east, as the Earth turns: the land in front drifts right.
        center -= (dt * 2 * Math.PI) / TURN_S
      }
      finds = finds.filter((f) => now - f.born < f.life)
      if (!target && now >= nextFind) {
        // A new find on land near the front, where it can be seen.
        const front = LAND.filter((cell) => project(cell, center).z > 0.6)
        if (front.length) finds.push({ cell: front[Math.floor(Math.random() * front.length)], born: now, life: FIND_LIFE_S })
        nextFind = now + FIND_EVERY_S
      }
      draw(ctx, size, center, finds, now)
      frame = requestAnimationFrame(tick)
    }

    const sizer = new ResizeObserver(resize)
    sizer.observe(el)
    resize()
    if (still) return () => sizer.disconnect()

    const watcher = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting
      cancelAnimationFrame(frame)
      last = 0
      if (visible) frame = requestAnimationFrame(tick)
    })
    watcher.observe(el)
    return () => {
      cancelAnimationFrame(frame)
      watcher.disconnect()
      sizer.disconnect()
    }
  }, [still])

  return <canvas ref={canvas} aria-hidden className="aspect-square w-full max-w-sm" />
}
