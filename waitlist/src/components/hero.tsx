import { useEffect, useRef, useState, type RefObject } from 'react'

import { SignupCard } from '../features/signup/signup-card'
import { prefersStill } from '../lib/motion'
import type { PilotSpots } from '../lib/api'
import { DEMO_VIDEO } from './demo-video'
import { HeroGlow } from './hero-glow'
import { Lace } from './lace-mascot'
import { ProductDemo } from './product-demo'
import { RotatingWord } from './rotating-word'

// What Lace finds, one after another; read whole without motion.
const FINDS = ['leads.', 'opportunities.', 'partners.', 'next deal.']

/** How far Lace's eyes turn towards the pointer, in its viewBox units. */
const LOOK_REACH = 8
/** Beyond this distance from Lace, its eyes turn all the way. */
const LOOK_FULL_PX = 320

/** Where Lace (in `el`) looks: towards the mouse, turning further the further
 * away it is; straight ahead without a mouse or with reduced motion. */
function useLookAtPointer(el: RefObject<HTMLElement | null>): { x: number; y: number } | null {
  const [look, setLook] = useState<{ x: number; y: number } | null>(null)
  useEffect(() => {
    if (prefersStill()) return
    let frame = 0
    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse' || frame) return
      frame = requestAnimationFrame(() => {
        frame = 0
        const box = el.current?.getBoundingClientRect()
        if (!box) return
        const dx = event.clientX - (box.left + box.width / 2)
        const dy = event.clientY - (box.top + box.height / 2)
        const dist = Math.hypot(dx, dy) || 1
        const reach = LOOK_REACH * Math.min(1, dist / LOOK_FULL_PX)
        setLook({ x: (dx / dist) * reach, y: (dy / dist) * reach })
      })
    }
    window.addEventListener('pointermove', onMove)
    return () => {
      window.removeEventListener('pointermove', onMove)
      cancelAnimationFrame(frame)
    }
  }, [el])
  return look
}

export function Hero({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  const hero = useRef<HTMLElement>(null)
  const mascot = useRef<HTMLSpanElement>(null)
  const look = useLookAtPointer(mascot)
  return (
    <section ref={hero} id="top" className="hero-paper relative isolate flex min-h-[calc(100svh-3.5rem)] items-center overflow-hidden">
      <HeroGlow hero={hero} />
      <div className="mx-auto grid w-full max-w-7xl gap-14 px-5 py-14 sm:px-8 short:py-8 lg:grid-cols-[0.95fr_1.15fr] lg:items-center lg:gap-16">
        <div className="flex min-w-0 flex-col gap-6 short:gap-4">
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
        <div className="min-w-0">
          <ProductDemo video={DEMO_VIDEO} />
        </div>
      </div>
    </section>
  )
}
