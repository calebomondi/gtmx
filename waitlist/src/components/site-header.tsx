import { useEffect, useRef, useState } from 'react'

import type { PilotSpots } from '../lib/api'
import { BrandMark } from './brand-mark'

const LINKS = [
  { href: '#what-lace-does', label: 'What it does' },
  { href: '#teams', label: 'For teams' },
  { href: '#pilot', label: 'Pilot' },
] as const

/** Past this much scroll the header floats as a bar. */
const FLOAT_AFTER_PX = 8

/** Whether the page has left its very top, which linked section the reader
 * is in (by the screen's upper third), and how far down the page they've
 * read, followed once a frame. The reading line is filled directly, outside
 * React's render; the rest is state, which changes far less often. */
function usePagePlace() {
  const reading = useRef<HTMLSpanElement>(null)
  const [place, setPlace] = useState<{ floating: boolean; active: number | null }>({ floating: false, active: null })
  useEffect(() => {
    const line = reading.current
    let frame = 0
    const update = () => {
      frame = 0
      const run = document.documentElement.scrollHeight - window.innerHeight
      if (line) line.style.transform = `scaleX(${run > 0 ? Math.min(1, window.scrollY / run) : 0})`
      const third = window.innerHeight / 3
      const passed = LINKS.findLastIndex(({ href }) => {
        const section = document.querySelector(href)
        return section !== null && section.getBoundingClientRect().top <= third
      })
      const next = { floating: window.scrollY > FLOAT_AFTER_PX, active: passed < 0 ? null : passed }
      setPlace((now) => (now.floating === next.floating && now.active === next.active ? now : next))
    }
    const schedule = () => { frame ||= requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
    }
  }, [])
  return { reading, ...place }
}

/** The header. On the hero it sits open on the page's paper, with no bar;
 * once the page scrolls it eases into a bar floating below the top of the
 * screen. The section you're in is lit, and the Pilot link says how many
 * pilot spots are left. It keeps its 56 px slot either way, so the pinned
 * scroll scenes sit where they always have. */
export function SiteHeader({ pilot }: { pilot: PilotSpots | null }) {
  const { reading, floating, active } = usePagePlace()
  const left = pilot && pilot.left > 0 ? pilot.left : null
  return (
    <header className={`sticky top-0 z-20 h-14 ${floating ? 'pt-2.5' : 'header-veil'}`}>
      {/* The same column as the sections, so the floating bar lines up with them. */}
      <div className={`header-bar mx-auto max-w-7xl ${floating ? 'px-2.5 sm:px-8' : 'px-5 sm:px-8'}`}>
        <div className={`header-bar relative flex items-center justify-between ${floating
          ? 'header-pill h-12 overflow-hidden rounded-xl bg-paper/95 pr-2 pl-5 shadow-lift ring-1 ring-ink/10 backdrop-blur-md'
          : 'h-14'}`}>
          <a href="#top" aria-label="Thalace home" className="relative">
            <BrandMark />
          </a>
          <nav className="relative flex items-center gap-5 text-sm">
            {LINKS.map((link, i) => (
              <a key={link.href} href={link.href} aria-current={active === i ? 'location' : undefined}
                 className={`hidden items-center gap-1.5 transition-colors sm:inline-flex ${
                   active === i ? 'font-medium text-ink' : 'text-muted hover:text-ink'}`}>
                {link.label}
                {link.href === '#pilot' && left !== null && (
                  <span className="rounded bg-brand px-1.5 py-px text-[11px] font-semibold text-ink tabular-nums">
                    {left} spots
                  </span>
                )}
              </a>
            ))}
            <a href="#join" className="btn-primary px-3.5 py-1.5 text-sm">
              Join the waitlist
            </a>
          </nav>
          {/* How far down the page you've read, along the bar's lower edge. */}
          <span ref={reading} aria-hidden
                className={`absolute bottom-0 left-0 h-[2px] w-full origin-left bg-brand transition-opacity ${floating ? '' : 'opacity-0'}`} />
        </div>
      </div>
    </header>
  )
}
