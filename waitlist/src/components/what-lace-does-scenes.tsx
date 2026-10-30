import { useEffect, useState, type CSSProperties } from 'react'

import { Lace } from './lace-mascot'

/** A scene plays from its first frame, or shows only its last one. */
export interface SceneProps {
  still: boolean
}

const DOT_COLS = 9
const DOT_ROWS = 3
/** The dot that turns out to be a find, counted across the rows. */
const FOUND_DOT = 15

/** When an animated element starts, in seconds from the scene's start. */
function at(seconds: number): CSSProperties {
  return { '--at': `${seconds}s` } as CSSProperties
}

/** False until `ms` into the scene; true at once when it's still. */
function useAfter(still: boolean, ms: number): boolean {
  const [done, setDone] = useState(still)
  useEffect(() => {
    if (still) return
    const timer = window.setTimeout(() => setDone(true), ms)
    return () => window.clearTimeout(timer)
  }, [still, ms])
  return done
}

/** Finds: Lace scans a field of dots; one lights up and becomes a lead. */
export function FindsScene({ still }: SceneProps) {
  const found = useAfter(still, 1400)
  const play = (name: string) => (still ? '' : name)
  return (
    <div className="relative flex h-full flex-col justify-between">
      <div className="relative">
        <div className="grid w-fit gap-x-3 gap-y-2.5" style={{ gridTemplateColumns: `repeat(${DOT_COLS}, auto)` }}>
          {Array.from({ length: DOT_COLS * DOT_ROWS }, (_, i) => (
            <span key={i} className={`size-1.5 rounded-full ${
              i === FOUND_DOT ? `bg-brand ${play('dot-light')}` : 'bg-ink/15'}`} style={i === FOUND_DOT ? at(1.1) : undefined} />
          ))}
        </div>
        {!still && <span aria-hidden className="scan-sweep absolute inset-y-[-6px] w-10" />}
        <div className="absolute top-0 right-0">
          <Lace state={found ? 'alert' : 'thinking'} size={28} decorative />
        </div>
      </div>
      <div className={`rounded-md border border-line bg-paper px-3 py-2 shadow-lift ${play('rise-in')}`} style={at(1.5)}>
        <p className="text-[11px] font-medium text-brand-ink">Lead, strong fit</p>
        <p className="text-sm font-semibold leading-tight">Acme Pay</p>
        <p className="text-xs text-muted">Raised a seed round in June</p>
      </div>
    </div>
  )
}

/** Watches: a rival cuts its price, and Lace flags it. */
export function WatchesScene({ still }: SceneProps) {
  const flagged = useAfter(still, 1800)
  const play = (name: string) => (still ? '' : name)
  return (
    <div className="flex h-full flex-col justify-between">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted">A rival’s Pro plan</p>
          <p className="mt-1 flex items-baseline gap-2.5">
            <span className={`relative text-2xl font-semibold tracking-tight text-muted ${play('price-old')}`} style={at(0.9)}>
              $12
              <span aria-hidden className={`absolute inset-x-[-2px] top-1/2 h-0.5 bg-dropped ${play('strike-in')}`} style={at(0.9)} />
            </span>
            <span className={`text-2xl font-semibold tracking-tight ${play('rise-in')}`} style={at(1.2)}>$9</span>
            <span className={`text-xs text-muted ${play('rise-in')}`} style={at(1.2)}>a seat</span>
          </p>
        </div>
        <Lace state={flagged ? 'alert' : 'idle'} size={28} decorative />
      </div>
      <p className={`flex w-fit items-center gap-2 rounded-full bg-highlight px-3 py-1.5 text-[13px] font-medium ${play('rise-in')}`} style={at(1.8)}>
        <span aria-hidden className="size-1.5 rounded-full bg-brand-deep" />
        Price cut, flagged for you
      </p>
    </div>
  )
}

const LONG_DRAFT = 'Hi Neema, congratulations on Acme Pay’s seed round. A first sales hire often spends months building lead lists by hand, and we…'
const SHORT_DRAFT = 'Hi Neema, congrats on the seed round. Worth 15 minutes next week?'

/** Works with you: a cofounder asks for it shorter, and the draft shrinks. */
export function DraftScene({ still }: SceneProps) {
  const rewritten = useAfter(still, 1700)
  const play = (name: string) => (still ? '' : name)
  return (
    <div className="flex h-full flex-col justify-between gap-2">
      <div className="rounded-md border border-dashed border-brand bg-paper px-3 py-2">
        {/* Both versions share one cell, so the card keeps its size as one replaces the other. */}
        <div className="grid text-[13px] leading-snug *:[grid-area:1/1]">
          <p className={still ? 'invisible' : 'fade-out'} style={at(1.5)}>{LONG_DRAFT}</p>
          <p className={play('rise-in')} style={at(1.7)}>{SHORT_DRAFT}</p>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5">
          <Lace state={rewritten ? 'idle' : 'thinking'} size={20} decorative />
          <span className={`text-xs font-medium text-kept ${play('rise-in')}`} style={at(2.2)}>✓ Shorter, same ask</span>
        </p>
        <p className={`flex items-center gap-1.5 ${play('rise-in')}`} style={at(0.5)}>
          <span className="rounded-md bg-highlight px-2 py-0.5 text-xs">Make it shorter</span>
          <span className="grid size-5 place-items-center rounded-full bg-ink text-[10px] font-semibold text-paper">C</span>
        </p>
      </div>
    </div>
  )
}
