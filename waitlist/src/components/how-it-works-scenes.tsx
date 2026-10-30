import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'

import { Lace, type LaceState } from './lace-mascot'

/** A scene plays from its first frame, or shows only its last one: before it
 * is on screen, and always with reduced motion. */
export interface SceneProps {
  still: boolean
}

/** How long the print takes, as in the .print-* animations (index.css). */
const PRINT_MS = 2600
/** Where Lace glances while nobody's pointer is near: Send, then you. */
const GLANCES = [{ x: 9, y: 5 }, { x: 0, y: 0 }]
const GLANCE_MS = 1100
const LOOK_REACH = 9
/** The round trip: the draft goes at SENT_MS, the reply is in at REPLIED_MS. */
const SENT_MS = 2600
const REPLIED_MS = 4200

/** When a rising element arrives, in seconds from the scene's start. */
function at(seconds: number): CSSProperties {
  return { '--at': `${seconds}s` } as CSSProperties
}

const LEARNED = [
  { label: 'Sells', value: 'An AI assistant for startups' },
  { label: 'To', value: 'Founding teams' },
  { label: 'Stands out', value: 'Shared by the whole team' },
]

/** Step 1: Lace is printed while its name and website type in, then shows
 * what it learned; it's confirmed, and a cofounder joins. */
export function BornScene({ still }: SceneProps) {
  const [printed, setPrinted] = useState(still)
  const rise = still ? '' : 'rise-in'

  useEffect(() => {
    if (still) return
    const timer = window.setTimeout(() => setPrinted(true), PRINT_MS)
    return () => window.clearTimeout(timer)
  }, [still])

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 sm:flex-row sm:gap-8">
      <div className="flex flex-col items-center gap-4">
        <div className="relative size-[88px]">
          {/* What isn't printed yet: faint layer lines where the body will be. */}
          {!printed && <div aria-hidden className="print-ghost absolute inset-0 rounded-[9%]" />}
          <div className={still ? '' : `print-fill absolute inset-0 ${printed ? 'pop-in' : ''}`}>
            <Lace state={printed ? 'alert' : 'sleepy'} size={88} decorative />
          </div>
          {!printed && <div aria-hidden className="print-nozzle absolute inset-x-[-12%] h-0.5 rounded-full bg-brand" />}
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono text-xs">
          <dt className="text-muted">Name</dt>
          <dd>{still ? 'Lace' : <span className="type-in" style={{ '--chars': 4 } as CSSProperties}>Lace</span>}</dd>
          <dt className="text-muted">Website</dt>
          <dd>
            {still ? 'thalace.com'
              : <span className="type-in type-in-late" style={{ '--chars': 11 } as CSSProperties}>thalace.com</span>}
          </dd>
        </dl>
      </div>
      <div className="flex w-60 flex-col gap-2.5">
        <div className="rounded-xl border border-line bg-panel p-4 shadow-lift">
          <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">What it learned</p>
          <dl className="mt-2.5 flex flex-col gap-2">
            {LEARNED.map((row, i) => (
              <div key={row.label} className={rise} style={at(2.9 + i * 0.45)}>
                <dt className="font-mono text-[10px] uppercase tracking-wider text-muted">{row.label}</dt>
                <dd className="text-[13px] font-medium leading-snug">{row.value}</dd>
              </div>
            ))}
          </dl>
          <span className={`mt-3.5 inline-flex rounded-md px-2.5 py-1 text-xs font-semibold ${
            still ? 'bg-kept text-panel' : 'confirm-in bg-ink text-paper'}`} style={at(4.5)}>
            ✓ Looks right
          </span>
        </div>
        <p className={`flex items-center gap-2 text-[13px] ${rise}`} style={at(5.3)}>
          <span className="grid size-6 place-items-center rounded-full bg-ink text-[11px] font-semibold text-paper">C</span>
          Your cofounder joined
        </p>
      </div>
    </div>
  )
}

const FINDS = [
  { tag: 'Lead', text: 'Acme Pay' },
  { tag: 'Event', text: 'Closes in 12 days' },
  { tag: 'Grant', text: 'Open to seed-stage teams' },
  { tag: 'Competitor', text: 'Changed its pricing' },
]
const FIND_ROW_PX = 60

/** A small clock whose hand ticks round: the work runs on a schedule. */
function Clock({ ticking }: { ticking: boolean }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-3.5" fill="none" stroke="currentColor" strokeWidth={2}
         strokeLinecap="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 12V7" className={ticking ? 'clock-tick' : ''} />
    </svg>
  )
}

/** Step 2: Lace thinks, and finds swoop out of it into a stack, on a
 * schedule. Each starts at Lace: to its left on wide screens, above it on
 * phones (the --fy-* offsets, read in .find-swoop). */
export function OrbitScene({ still }: SceneProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 sm:flex-row sm:gap-8">
      <div className="flex shrink-0 flex-col items-center gap-3">
        <div className="relative grid size-[150px] place-items-center">
          <div aria-hidden className={`absolute inset-0 rounded-full border-2 border-dashed border-brand/70 ${still ? '' : 'spin-slow'}`} />
          <Lace state="thinking" size={96} decorative />
        </div>
        <p className="flex items-center gap-1.5 rounded-full border border-line bg-panel px-2.5 py-1 font-mono text-[11px] text-muted">
          <Clock ticking={!still} /> Every Monday, 9:00
        </p>
      </div>
      <ul className="flex w-52 flex-col gap-2">
        {FINDS.map((find, i) => (
          <li key={find.tag} className={`rounded-lg border border-line bg-panel px-3 py-2 shadow-lift ${still ? '' : 'find-swoop'}`}
              style={{
                ...at(0.5 + i * 0.8),
                '--fy-row': `${(1.5 - i) * FIND_ROW_PX}px`,
                '--fy-col': `${-(150 + i * FIND_ROW_PX)}px`,
              } as CSSProperties}>
            <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">{find.tag}</p>
            <p className="text-sm font-semibold leading-tight">{find.text}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}

type Trip = 'waiting' | 'sent' | 'replied'

const TRIP_MOOD: Record<Trip, LaceState> = { waiting: 'idle', sent: 'thinking', replied: 'alert' }
const TRIP_SAYS: Record<Trip, string> = { waiting: 'Your call.', sent: 'Sent.', replied: 'Neema replied.' }

function PaperPlane() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="plane-fly absolute right-2 bottom-3 size-7 text-ink" fill="none"
         stroke="currentColor" strokeWidth={1.75} strokeLinejoin="round">
      <path d="M21 3 3 10.5l7 2.5 2.5 7L21 3Z" fill="var(--color-highlight)" />
      <path d="m10 13 4.5-4.5" />
    </svg>
  )
}

/** Step 3: Lace waits on your call, eyes on Send and on you (they follow
 * your pointer). Send goes, the draft flies off as a paper plane, and the
 * reply comes back with an answer drafted. */
export function RoundTripScene({ still }: SceneProps) {
  const stage = useRef<HTMLDivElement>(null)
  const [trip, setTrip] = useState<Trip>(still ? 'replied' : 'waiting')
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null)
  const [glance, setGlance] = useState(0)

  useEffect(() => {
    if (still) return
    const timers = [
      window.setTimeout(() => setTrip('sent'), SENT_MS),
      window.setTimeout(() => setTrip('replied'), REPLIED_MS),
    ]
    return () => timers.forEach((t) => window.clearTimeout(t))
  }, [still])

  useEffect(() => {
    if (still || pointer || trip !== 'waiting') return
    const timer = window.setInterval(() => setGlance((g) => (g + 1) % GLANCES.length), GLANCE_MS)
    return () => window.clearInterval(timer)
  }, [still, pointer, trip])

  const follow = (event: PointerEvent<HTMLDivElement>) => {
    const box = stage.current?.getBoundingClientRect()
    if (!box || still) return
    // From the stage's centre, scaled to how far the eyes can turn.
    const x = ((event.clientX - box.left) / box.width - 0.5) * 2 * LOOK_REACH
    const y = ((event.clientY - box.top) / box.height - 0.5) * 2 * LOOK_REACH
    setPointer({ x: Math.max(-LOOK_REACH, Math.min(LOOK_REACH, x)), y: Math.max(-LOOK_REACH, Math.min(LOOK_REACH, y)) })
  }
  const look = still ? null : pointer ?? (trip === 'waiting' ? GLANCES[glance] : null)

  return (
    <div ref={stage} onPointerMove={follow} onPointerLeave={() => setPointer(null)}
         className="flex h-full flex-col items-center justify-center gap-5 sm:flex-row sm:gap-8">
      <div className="flex flex-col items-center gap-3">
        <Lace state={TRIP_MOOD[trip]} size={96} look={look} decorative />
        <p className="rounded-full border border-line bg-panel px-3 py-1 text-xs">{TRIP_SAYS[trip]}</p>
      </div>
      {/* The draft and the reply share one cell, so the scene keeps its size as one replaces the other. */}
      <div className="relative grid w-60 *:[grid-area:1/1]">
        <div className={`self-center rounded-lg border border-dashed border-brand bg-panel p-3 ${
          trip === 'waiting' ? '' : still ? 'invisible' : 'fly-off'}`}>
          <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">Draft · to Neema by email</p>
          <p className="mt-1.5 text-[13px] leading-snug">Hi Neema, congrats on Acme Pay’s seed round. Worth 15 minutes next week?</p>
          <div className="mt-3 flex justify-end">
            <span className={`rounded-md px-3 py-1 text-xs font-semibold ${
              trip === 'waiting' ? 'send-wait bg-ink text-paper' : 'bg-brand text-ink'}`}>Send</span>
          </div>
        </div>
        {trip === 'sent' && <PaperPlane />}
        <div className={`self-center rounded-lg border border-line bg-panel p-3 shadow-lift ${
          trip !== 'replied' ? 'invisible' : still ? '' : 'rise-in'}`}>
          <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">Reply · from Neema</p>
          <p className="mt-1.5 text-[13px] leading-snug">“Tuesday works. Can my cofounder join the call?”</p>
          <div className="mt-2.5 flex items-center justify-between border-t border-line pt-2.5">
            <span className="flex items-center gap-1.5 text-xs font-medium">
              <span aria-hidden className="size-1.5 rounded-full bg-kept" /> Answer drafted
            </span>
            <span className="rounded-md bg-ink px-2.5 py-1 text-xs font-semibold text-paper">Review</span>
          </div>
        </div>
      </div>
    </div>
  )
}
