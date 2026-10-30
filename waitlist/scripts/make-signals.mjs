// Writes public/bg/signals.svg: the "field of signals" behind What your Lace
// does, a tile of unevenly scattered dots, a few of them lit as finds. Run
// from waitlist/: `bun scripts/make-signals.mjs`.
//
// Seeded, so the tile is the same on every run. Points are kept apart by a
// minimum gap, which reads as scattered rather than clumped.
import { writeFileSync } from 'node:fs'

const SIZE = 320
const DOTS = 70
const MIN_GAP = 18
const LIT_EVERY = 11
const INK = '#121212'
const BRAND = '#fea853'

let seed = 7
const random = () => {
  seed = (seed * 16807) % 2147483647
  return (seed - 1) / 2147483646
}

// The generator's first draws sit near zero; skip them.
for (let i = 0; i < 5; i++) random()

const points = []
for (let tries = 0; points.length < DOTS && tries < 5000; tries++) {
  const p = { x: random() * SIZE, y: random() * SIZE }
  // Measured across the tile's edges too, so repeats don't crowd at the seams.
  const near = points.some((q) => {
    const dx = Math.min(Math.abs(p.x - q.x), SIZE - Math.abs(p.x - q.x))
    const dy = Math.min(Math.abs(p.y - q.y), SIZE - Math.abs(p.y - q.y))
    return Math.hypot(dx, dy) < MIN_GAP
  })
  if (!near) points.push(p)
}

const dots = points.map((p, i) => {
  const lit = i % LIT_EVERY === 0
  const r = lit ? 2.6 : 1 + random() * 0.9
  const fill = lit ? BRAND : INK
  const opacity = lit ? 0.9 : (0.12 + random() * 0.14).toFixed(2)
  return `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${r.toFixed(1)}" fill="${fill}" fill-opacity="${opacity}"/>`
})

writeFileSync(
  new URL('../public/bg/signals.svg', import.meta.url),
  `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 ${SIZE} ${SIZE}">${dots.join('')}</svg>\n`,
)
