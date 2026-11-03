import { useEffect, useRef, type RefObject } from 'react'

import { SignupCard } from '../features/signup/signup-card'
import { useLookAtPointer } from '../lib/use-look-at-pointer'
import type { PilotSpots } from '../lib/api'
import { ease, HEADER_PX, useScrollScenes, watchProgress } from '../lib/use-scroll-progress'
import { DEMO_VIDEO } from './demo-video'
import { HeroRadar } from './hero-radar'
import { Lace } from './lace-mascot'
import { ProductDemo } from './product-demo'
import { RotatingWord } from './rotating-word'

// What Lace finds, one after another; read whole without motion.
const FINDS = ['leads.', 'opportunities.', 'partners.', 'next deal.']

/** Widest the demo grows to, and the room kept around it when it has. */
const HANDOFF_MAX_PX = 1160
const HANDOFF_MARGIN_PX = 48

/** The hero hands over to the product as the page scrolls: the hero pins,
 * the words step aside, and the demo grows from its column to the middle of
 * the screen, the squares around it drawn in towards it. Scrolling back
 * reverses it. Wide screens with motion only; elsewhere the hero is as it
 * was. Styles are set outside React's render, once a frame. */
function useHandoff(hero: RefObject<HTMLElement | null>, copy: RefObject<HTMLDivElement | null>,
                    slot: RefObject<HTMLDivElement | null>) {
  const track = useRef<HTMLDivElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const progress = useRef(0)
  const handoff = useScrollScenes()

  useEffect(() => {
    const inner = stage.current
    const words = copy.current
    const el = track.current
    if (!inner || !words || !el) return
    if (!handoff) {
      // Back to the plain hero (a narrow window, or reduced motion).
      progress.current = 0
      inner.removeAttribute('style')
      words.removeAttribute('style')
      return
    }
    return watchProgress(el, (raw) => {
      const p = ease(raw)
      progress.current = p
      const area = hero.current?.getBoundingClientRect()
      const box = slot.current?.getBoundingClientRect()
      if (!area || !box?.width) return
      const roomH = window.innerHeight - HEADER_PX - 2 * HANDOFF_MARGIN_PX
      const width = Math.min(window.innerWidth - 2 * HANDOFF_MARGIN_PX, HANDOFF_MAX_PX, roomH * (box.width / box.height))
      const scale = 1 + (width / box.width - 1) * p
      const dx = (window.innerWidth / 2 - (box.left + box.width / 2)) * p
      const dy = (area.top + area.height / 2 - (box.top + box.height / 2)) * p
      inner.style.transform = p ? `translate(${dx}px, ${dy}px) scale(${scale})` : ''
      words.style.opacity = p ? String(Math.max(0, 1 - p * 1.8)) : ''
      words.style.transform = p ? `translateX(${-56 * p}px)` : ''
      // The signup can't be clicked while it fades out.
      words.style.pointerEvents = p > 0.3 ? 'none' : ''
    })
  }, [handoff, hero, copy, slot])

  return { track, stage, handoff, progress }
}

export function Hero({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  const hero = useRef<HTMLElement>(null)
  const mascot = useRef<HTMLSpanElement>(null)
  const copy = useRef<HTMLDivElement>(null)
  const demo = useRef<HTMLDivElement>(null)
  const look = useLookAtPointer(mascot)
  const { track, stage, handoff, progress } = useHandoff(hero, copy, demo)
  return (
    <div ref={track} className={handoff ? 'h-[calc(175dvh-3.5rem)]' : ''}>
    <section ref={hero} id="top"
             className={`hero-paper relative isolate flex min-h-[calc(100dvh-3.5rem)] items-center overflow-hidden ${
               handoff ? 'sticky top-14 h-[calc(100dvh-3.5rem)]' : ''}`}>
      <HeroRadar hero={hero} origin={mascot} copy={copy} demo={demo} pull={progress} />
      <div className="mx-auto grid w-full max-w-7xl gap-14 px-5 py-14 sm:px-8 short:py-8 lg:grid-cols-[0.95fr_1.15fr] lg:items-center lg:gap-16">
        <div ref={copy} className="flex min-w-0 flex-col gap-6 short:gap-4">
          <div className="flex flex-col gap-3">
            <h1 className="text-[2.75rem] leading-[1.02] font-semibold tracking-[-0.035em] text-balance sm:text-[4.1rem] short:text-[2.6rem]">
              Meet{' '}
              {/* Lace itself, after its name, kept on one line with the comma; sized
                  to the letters, so it scales with them. */}
              <span ref={mascot} className="whitespace-nowrap">
                Lace
                <Lace state="idle" size={64} look={look} decorative className="mx-[0.1em] inline-block size-[0.72em] align-baseline" />,
              </span>{' '}
              your startup’s AI assistant.
            </h1>
            <p className="text-2xl leading-tight font-semibold tracking-tight sm:text-3xl short:text-xl">
              It finds your{' '}
              <RotatingWord words={FINDS} whole="leads, opportunities, partners and your next deal." />
            </p>
          </div>
          <p className="max-w-xl text-lg leading-relaxed text-muted short:text-base">
            <span className="font-medium text-ink">One Lace for your startup, shared by your whole founding team.</span>{' '}
            It finds leads, partners and funding, watches competitors, and drafts every message.{' '}
            <strong className="font-semibold text-ink">Nothing goes out without your click.</strong>
          </p>
          <SignupCard id="join" pilot={pilot} onPilotSpotsLeft={onPilotSpotsLeft} />
          {pilot && pilot.left > 0 && (
            <p className="flex items-center gap-2 text-[13px] font-medium">
              <span aria-hidden className="size-2 rounded-[2px] bg-ink" />
              {pilot.left} of {pilot.total} pilot spots open
            </p>
          )}
        </div>
        <div ref={demo} className="min-w-0">
          <div ref={stage} className="relative z-10 origin-center will-change-transform">
            <ProductDemo video={DEMO_VIDEO} />
          </div>
        </div>
      </div>
    </section>
    </div>
  )
}
