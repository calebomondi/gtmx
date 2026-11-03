import { useEffect, useState } from 'react'

import type { PilotSpots } from '../lib/api'
import { BrandMark } from './brand-mark'

const LINKS = [
  { href: '#what-lace-does', label: 'What it does' },
  { href: '#teams', label: 'For teams' },
  { href: '#pilot', label: 'Pilot' },
] as const

/** Past this much scroll the header floats as a pill. */
const FLOAT_AFTER_PX = 8

/** Whether the page has left its very top, and which linked section the
 * reader is in (by the screen's upper third), followed once a frame. */
function usePagePlace(): { floating: boolean; active: number | null } {
  const [place, setPlace] = useState<{ floating: boolean; active: number | null }>({ floating: false, active: null })
  useEffect(() => {
    let frame = 0
    const update = () => {
      frame = 0
      const line = window.innerHeight / 3
      const passed = LINKS.findLastIndex(({ href }) => {
        const section = document.querySelector(href)
        return section !== null && section.getBoundingClientRect().top <= line
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
  return place
}

/** The header. On the hero it sits open on the page's paper, with no bar;
 * once the page scrolls it eases into a pill floating below the top of the
 * screen. The section you're in is lit, and the Pilot link says how many
 * pilot spots are left. It keeps its 56 px slot either way, so the pinned
 * scroll scenes sit where they always have. */
export function SiteHeader({ pilot }: { pilot: PilotSpots | null }) {
  const { floating, active } = usePagePlace()
  const left = pilot && pilot.left > 0 ? pilot.left : null
  return (
    <header className={`sticky top-0 z-20 h-14 ${floating ? 'pt-2.5' : 'header-veil'}`}>
      <div className={`header-bar flex items-center justify-between ${floating
        ? 'mx-2.5 h-11 max-w-[55rem] rounded-full bg-paper/95 pr-1.5 pl-5 shadow-lift ring-1 ring-ink/10 backdrop-blur-md sm:mx-auto'
        : 'mx-auto h-14 max-w-7xl px-5 sm:px-8'}`}>
        <a href="#top" aria-label="Thalace home">
          <BrandMark />
        </a>
        <nav className="flex items-center gap-5 text-sm">
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
          <a href="#join" className={`btn-primary text-sm ${floating ? 'rounded-full px-4 py-1.5' : 'px-3.5 py-1.5'}`}>
            Join the waitlist
          </a>
        </nav>
      </div>
    </header>
  )
}
