import { useEffect, useRef, useState } from 'react'

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

function prefersStill(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

interface Find {
  cell: Cell
  born: number
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
    const age = (now - find.born) / FIND_LIFE_S
    const side = cellSide * (0.5 + 0.5 * p.z)
    const x = cx + p.x * r
    const y = cy - p.y * r
    ctx.strokeStyle = `rgba(${BRAND_DEEP}, ${0.8 * (1 - age)})`
    ctx.lineWidth = 2
    const ring = side * (1 + 2.2 * age)
    ctx.strokeRect(x - ring / 2, y - ring / 2, ring, ring)
    ctx.fillStyle = `rgba(${INK}, ${age < 0.85 ? 1 : (1 - age) / 0.15})`
    ctx.fillRect(x - side / 2, y - side / 2, side, side)
  }
}

/** The world as square boxes on a slowly turning globe, with finds lighting
 * up on land as it turns. Turns only on screen; still with reduced motion. */
export function RotatingGlobe() {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [still] = useState(prefersStill)

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
      // West to east, as the Earth turns: the land in front drifts right.
      if (last) center -= ((now - last) * 2 * Math.PI) / TURN_S
      last = now
      finds = finds.filter((f) => now - f.born < FIND_LIFE_S)
      if (now >= nextFind) {
        // A new find on land near the front, where it can be seen.
        const front = LAND.filter((cell) => project(cell, center).z > 0.6)
        if (front.length) finds.push({ cell: front[Math.floor(Math.random() * front.length)], born: now })
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
