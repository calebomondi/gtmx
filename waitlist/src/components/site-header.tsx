import { useEffect, useRef, useState } from 'react'

import type { PilotSpots } from '../lib/api'
import { BrandMark } from './brand-mark'
import { Lace } from './lace-mascot'

const LINKS = [
  { href: '#what-lace-does', label: 'What it does' },
  { href: '#teams', label: 'For teams' },
  { href: '#pilot', label: 'Pilot' },
] as const

/** Lace riding the header's line, in px. */
const RIDER_PX = 16

interface Progress {
  /** Where each linked section starts along the page (0–1), for its tick. */
  ticks: number[]
  /** The linked section the page is in, if any. */
  active: number | null
}

/** How far down the page the reader is, followed once a frame: Lace is
 * moved along the line directly, and the ticks and the active section,
 * which change far less often, are state. */
function usePageProgress() {
  const rider = useRef<HTMLSpanElement>(null)
  const [progress, setProgress] = useState<Progress>({ ticks: [], active: null })
  useEffect(() => {
    const el = rider.current
    if (!el) return
    let frame = 0
    const update = () => {
      frame = 0
      const run = document.documentElement.scrollHeight - window.innerHeight
      const p = run > 0 ? Math.min(1, Math.max(0, window.scrollY / run)) : 0
      const line = el.parentElement?.clientWidth ?? 0
      el.style.transform = `translateX(${p * (line - RIDER_PX)}px)`
      const ticks = LINKS.map(({ href }) => {
        const section = document.querySelector(href)
        return section && run > 0 ? Math.min(1, (section.getBoundingClientRect().top + window.scrollY) / run) : 0
      })
      const passed = ticks.findLastIndex((t) => p >= t - 0.002)
      const active = passed < 0 ? null : passed
      setProgress((now) => (now.active === active && now.ticks.length === ticks.length
        && now.ticks.every((t, i) => Math.abs(t - ticks[i]) < 0.001) ? now : { ticks, active }))
    }
    const schedule = () => { frame ||= requestAnimationFrame(update) }
    update()
    // Fonts, the pilot count and the scroll scenes settle the page's length late.
    void document.fonts?.ready.then(schedule)
    const grown = new ResizeObserver(schedule)
    grown.observe(document.body)
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    return () => {
      cancelAnimationFrame(frame)
      grown.disconnect()
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
    }
  }, [])
  return { rider, ...progress }
}

/** The header: the mark, the sections, and the signup, which says how many
 * pilot spots are left. Its bottom line is the page's progress: Lace rides
 * it as you scroll, ticks mark where each section starts, and the section
 * you're in is lit in the nav. */
export function SiteHeader({ pilot }: { pilot: PilotSpots | null }) {
  const { rider, ticks, active } = usePageProgress()
  const left = pilot && pilot.left > 0 ? pilot.left : null
  return (
    <header className="sticky top-0 z-20 bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-5 sm:px-8">
        <a href="#top" aria-label="Thalace home">
          <BrandMark />
        </a>
        <nav className="flex items-center gap-5 text-sm">
          {LINKS.map((link, i) => (
            <a key={link.href} href={link.href} aria-current={active === i ? 'location' : undefined}
               className={`hidden transition-colors sm:inline ${active === i ? 'font-medium text-ink' : 'text-muted hover:text-ink'}`}>
              {link.label}
            </a>
          ))}
          <a href="#join" className="btn-primary gap-2 px-3.5 py-1.5 text-sm">
            Join the waitlist
            {left !== null && (
              <span className="rounded bg-brand px-1.5 py-px text-[11px] font-semibold text-ink tabular-nums">{left} left</span>
            )}
          </a>
        </nav>
      </div>
      {/* The page's progress: a hairline, ticks where sections start, Lace riding it. */}
      <div aria-hidden className="relative h-px bg-ink/10">
        {ticks.map((t, i) => (
          <span key={i} style={{ left: `${t * 100}%` }}
                className={`absolute -top-[3px] h-[7px] w-px transition-colors ${active !== null && i <= active ? 'bg-brand-ink' : 'bg-ink/25'}`} />
        ))}
        <span ref={rider} className="absolute top-[-8px] left-0 block will-change-transform">
          <Lace state="idle" size={RIDER_PX} decorative />
        </span>
      </div>
    </header>
  )
}
