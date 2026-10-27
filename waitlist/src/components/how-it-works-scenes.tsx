import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react'

import { Lace } from './lace-mascot'

const MASCOT_PX = 112
/** How long the print takes, as in the .print-* animations (index.css). */
const PRINT_MS = 2600
/** Where Lace glances while nobody's pointer is near: Send, then you. */
const GLANCES = [{ x: 9, y: 5 }, { x: 0, y: 0 }]
const GLANCE_MS = 2200
const LOOK_REACH = 9

function prefersStill(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Step 1: Lace is printed, layer by layer, then opens its eyes. */
export function CreatedScene() {
  const [still] = useState(prefersStill)
  const [printed, setPrinted] = useState(still)

  useEffect(() => {
    if (still) return
    const timer = window.setTimeout(() => setPrinted(true), PRINT_MS)
    return () => window.clearTimeout(timer)
  }, [still])

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6">
      <div className="relative" style={{ width: MASCOT_PX, height: MASCOT_PX }}>
        {/* What isn't printed yet: faint layer lines where the body will be. */}
        {!printed && <div aria-hidden className="print-ghost absolute inset-0 rounded-[9%]" />}
        <div className={`print-fill absolute inset-0 ${printed ? 'pop-in' : ''}`}>
          <Lace state={printed ? 'alert' : 'sleepy'} size={MASCOT_PX} decorative />
        </div>
        {!printed && <div aria-hidden className="print-nozzle absolute inset-x-[-12%] h-0.5 rounded-full bg-highlight" />}
      </div>
      <dl className="grid w-56 grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 font-mono text-xs">
        <dt className="text-night-muted">Name</dt>
        <dd><span className="type-in" style={{ '--chars': 4 } as CSSProperties}>Lace</span></dd>
        <dt className="text-night-muted">Website</dt>
        <dd><span className="type-in type-in-late" style={{ '--chars': 11 } as CSSProperties}>thalace.com</span></dd>
      </dl>
    </div>
  )
}

const FINDS = [
  { tag: 'Customer', text: 'Acme Pay' },
  { tag: 'Event', text: 'Closes in 12 days' },
  { tag: 'Competitor', text: 'Changed its pricing' },
]

/** Step 2: Lace thinks, and finds pop out of it into a stack. */
export function ThinkingScene() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 sm:flex-row sm:gap-8">
      <div className="relative grid shrink-0 place-items-center" style={{ width: MASCOT_PX * 1.6, height: MASCOT_PX * 1.6 }}>
        <div aria-hidden className="spin-slow absolute inset-0 rounded-full border-2 border-dashed border-brand/40" />
        <Lace state="thinking" size={MASCOT_PX} decorative />
      </div>
      <ul className="flex w-48 flex-col gap-2">
        {FINDS.map((find, i) => (
          <li key={find.tag} className="find-in rounded-lg bg-paper px-3 py-2 text-ink shadow-lift"
              style={{ animationDelay: `${0.6 + i * 0.9}s` }}>
            <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">{find.tag}</p>
            <p className="text-sm font-semibold leading-tight">{find.text}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Step 3: Lace stares, waiting for you. Its eyes follow your pointer; left
 * alone, it glances at Send and back at you. */
export function StareScene() {
  const stage = useRef<HTMLDivElement>(null)
  const [still] = useState(prefersStill)
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null)
  const [glance, setGlance] = useState(0)

  useEffect(() => {
    if (still || pointer) return
    const timer = window.setInterval(() => setGlance((g) => (g + 1) % GLANCES.length), GLANCE_MS)
    return () => window.clearInterval(timer)
  }, [still, pointer])

  const follow = (event: PointerEvent<HTMLDivElement>) => {
    const box = stage.current?.getBoundingClientRect()
    if (!box || still) return
    // From the stage's centre, scaled to how far the eyes can turn.
    const x = ((event.clientX - box.left) / box.width - 0.5) * 2 * LOOK_REACH
    const y = ((event.clientY - box.top) / box.height - 0.5) * 2 * LOOK_REACH
    setPointer({ x: Math.max(-LOOK_REACH, Math.min(LOOK_REACH, x)), y: Math.max(-LOOK_REACH, Math.min(LOOK_REACH, y)) })
  }

  return (
    <div ref={stage} onPointerMove={follow} onPointerLeave={() => setPointer(null)}
         className="flex h-full flex-col items-center justify-center gap-5 sm:flex-row sm:gap-6">
      <div className="flex flex-col items-center gap-3">
        <Lace state="idle" size={MASCOT_PX} look={still ? null : pointer ?? GLANCES[glance]} decorative />
        <p className="rounded-full bg-night-line px-3 py-1 text-xs text-paper">Your call.</p>
      </div>
      <div className="w-52 rounded-lg border border-dashed border-brand bg-paper p-3 text-ink">
        <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">Draft · to Neema by email</p>
        <p className="mt-1.5 text-[13px] leading-snug">Hi Neema, congrats on Acme Pay’s seed round. Worth 15 minutes next week?</p>
        <div className="mt-3 flex justify-end">
          <span className="send-wait rounded-md bg-ink px-3 py-1 text-xs font-semibold text-paper">Send</span>
        </div>
      </div>
    </div>
  )
}
