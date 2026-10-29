import { useEffect, useRef, useState, type ReactNode } from 'react'

import { DemoFrame } from './demo-frame'
import { Lace, type LaceState } from './lace-mascot'

// Thalace's own Lace at work. The startups it finds are invented: none is a real company or person.
const LACE = 'Lace'
const TICK_MS = 750

interface Scene {
  label: string
  /** Ticks the scene runs before the next one. */
  length: number
  /** The mascot's state at tick `t`. */
  mood: (t: number) => LaceState
  render: (t: number) => ReactNode
}

function prefersStill(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Shown from tick `at` on, rising in as it arrives. */
function At({ t, at, children }: { t: number; at: number; children: ReactNode }) {
  return t >= at ? <div className="word-in">{children}</div> : null
}

function Step({ done, children }: { done: boolean; children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 font-mono text-[11px] text-muted sm:text-xs">
      <span aria-hidden className={`grid size-3.5 place-items-center rounded-sm ${done ? 'bg-kept text-panel' : 'bg-brand caret'}`}>
        {done ? '✓' : ''}
      </span>
      {children}
    </p>
  )
}

function Card({ tag, title, children }: { tag: string; title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-3 shadow-lift sm:p-4">
      <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">{tag}</p>
      <p className="mt-1 font-semibold tracking-tight">{title}</p>
      <div className="mt-1.5 flex flex-col gap-1 text-[13px] leading-snug text-muted">{children}</div>
    </div>
  )
}

const LONG_DRAFT = 'Hi Neema, congratulations on Acme Pay’s seed round. A first sales hire often spends months building lead lists by hand. Lace finds the companies with a reason to buy now and drafts the first message, so your new hire is selling from week one. Would a 15-minute call next week be useful?'
const SHORT_DRAFT = 'Hi Neema, congrats on the seed round. Lace finds Acme Pay’s next customers and drafts the outreach, so your first sales hire sells from week one. Worth 15 minutes next week?'

const SCENES: Scene[] = [
  {
    label: 'Finds',
    length: 9,
    mood: (t) => (t < 5 ? 'thinking' : 'alert'),
    render: (t) => (
      <>
        <At t={t} at={0}><Step done={t >= 2}>Reading thalace.com</Step></At>
        <At t={t} at={1}><Step done={t >= 3}>Searching for startups that just raised a seed round</Step></At>
        <At t={t} at={2}><Step done={t >= 5}>Checking acmepay.example/careers</Step></At>
        <At t={t} at={5}>
          <Card tag="Lead · strong fit" title="Acme Pay">
            <p><span className="font-medium text-ink">Why now:</span> raised a seed round, hiring its first sales lead</p>
            <p><span className="font-medium text-ink">Reach:</span> Neema Okafor, founder &amp; CEO · email</p>
          </Card>
        </At>
      </>
    ),
  },
  {
    label: 'Spots',
    length: 8,
    mood: (t) => (t < 3 ? 'thinking' : 'alert'),
    render: (t) => (
      <>
        <At t={t} at={0}><Step done={t >= 3}>Scanning events, accelerators and partners</Step></At>
        <At t={t} at={3}>
          <Card tag="Showcase · pitch competition" title="Founders’ Pitch Night: applications open">
            <p>Closes in 12 days · fits: the room is seed-stage founders</p>
          </Card>
        </At>
        <At t={t} at={5}>
          <Card tag="Partner · accelerator" title="Launchpad accelerator: partner programme">
            <p>Closes in 3 weeks · its startups are the ones you sell to</p>
          </Card>
        </At>
      </>
    ),
  },
  {
    label: 'Drafts',
    length: 11,
    mood: (t) => (t >= 3 && t < 6 ? 'thinking' : 'idle'),
    render: (t) => (
      <>
        <div className="rounded-lg border border-dashed border-brand bg-panel p-3 sm:p-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">Draft · to Neema Okafor by email</p>
          <p className="mt-1.5 text-[13px] leading-snug">{t >= 6 ? SHORT_DRAFT : LONG_DRAFT}</p>
          <div className="mt-3 flex items-center justify-end gap-2">
            <Lace state={t >= 3 && t < 6 ? 'thinking' : 'idle'} size={22} decorative />
            <span className={`rounded-md bg-ink px-3 py-1 text-xs font-semibold text-paper ${t >= 8 ? 'ring-4 ring-brand' : ''}`}>
              Send
            </span>
          </div>
        </div>
        <At t={t} at={2}>
          {/* A cofounder weighs in: the Lace is the whole team's. */}
          <div className="ml-auto flex w-fit items-center gap-1.5">
            <p className="rounded-lg bg-highlight px-2.5 py-1 text-[13px]">Make it shorter</p>
            <span aria-label="Your cofounder" className="grid size-5 place-items-center rounded-full bg-ink text-[10px] font-semibold text-paper">C</span>
          </div>
        </At>
        <At t={t} at={6}>
          <p className="w-fit rounded-lg bg-panel px-2.5 py-1 text-[13px] text-muted shadow-lift">Cut it to three lines and kept the ask.</p>
        </At>
      </>
    ),
  },
]

/** The hero's example, until a recording is published: an invented Lace at
 * work, acted out in three short scenes (finding a lead, spotting an
 * opportunity, a draft brainstormed shorter). It plays only on screen; with
 * reduced motion each scene is shown whole and the tabs switch them. */
export function LacePreview() {
  const box = useRef<HTMLDivElement>(null)
  const [still] = useState(prefersStill)
  const [scene, setScene] = useState(0)
  const [tick, setTick] = useState(0)
  const [visible, setVisible] = useState(false)
  const current = SCENES[scene]
  const t = still ? current.length : tick

  useEffect(() => {
    if (!box.current) return
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.25 })
    observer.observe(box.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (still || !visible) return
    const timer = window.setInterval(() => setTick((n) => n + 1), TICK_MS)
    return () => window.clearInterval(timer)
  }, [still, visible])

  // Past its length, a scene hands over to the next.
  if (!still && tick >= current.length) {
    setTick(0)
    setScene((s) => (s + 1) % SCENES.length)
  }

  const pick = (next: number) => {
    setScene(next)
    setTick(0)
  }

  return (
    <DemoFrame status="Example" live={!still && visible} detail={`Thalace’s own ${LACE}, finding invented startups`}>
      {/* 4:3 like the recording that will replace it; on phones, tall enough for a whole scene. */}
      <div ref={box} className="flex min-h-[24rem] flex-col bg-paper sm:aspect-[4/3] sm:min-h-0">
        <div className="flex items-center gap-3 border-b border-line bg-panel px-4 py-3">
          <Lace state={current.mood(t)} size={32} decorative />
          <div className="min-w-0">
            <p className="text-sm font-semibold leading-tight">{LACE}</p>
            <p className="truncate text-xs text-muted">thalace.com</p>
          </div>
          <div className="ml-auto flex gap-1" role="tablist" aria-label="Example scenes">
            {SCENES.map((s, i) => (
              <button key={s.label} type="button" role="tab" aria-selected={i === scene} onClick={() => pick(i)}
                      className={`cursor-pointer rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors ${
                        i === scene ? 'bg-ink text-brand' : 'text-muted hover:text-ink'}`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
        {/* Remounts per scene, so each starts from its first line. */}
        <div key={scene} className="flex min-h-0 flex-1 flex-col justify-center gap-2.5 overflow-hidden p-4 sm:p-5" aria-live="off">
          {current.render(t)}
        </div>
      </div>
    </DemoFrame>
  )
}
