import { useEffect, useRef, useState, type CSSProperties } from 'react'

import { usePlay } from '../lib/motion'
import { stagger } from '../lib/stagger'
import { RotatingGlobe, type Place } from './rotating-globe'
import { LaceSquare } from './lace-square'
import { Section } from './section'

/** Reasons to reach out now, the kind Lace spots wherever you sell. */
const SIGNALS = [
  'funding rounds', 'new offices', 'tenders & RFPs', 'hiring pushes', 'product launches',
  'leadership moves', 'conferences', 'partnerships', 'growing communities', 'tool switches',
]

// What a founder might ask for, and where the globe turns to. Places only, no companies.
const ASKS: { ask: string; place: Place }[] = [
  { ask: 'Find me fintechs in Lisbon', place: { name: 'Lisbon', lat: 38.7, lon: -9.1 } },
  { ask: 'Find me clinics in Nairobi', place: { name: 'Nairobi', lat: -1.3, lon: 36.8 } },
  { ask: 'Find me retailers in São Paulo', place: { name: 'São Paulo', lat: -23.5, lon: -46.6 } },
  { ask: 'Find me logistics firms in Singapore', place: { name: 'Singapore', lat: 1.35, lon: 103.8 } },
]
/** When the typed ask has finished (the .type-in timing, index.css) and the globe turns. */
const TYPED_MS = 1200

/** Ask for a place and the globe turns there: once when it comes into view,
 * then whenever a place is picked. With reduced motion the ask shows whole
 * and the globe simply faces the place. */
function AskForAPlace() {
  const box = useRef<HTMLDivElement>(null)
  const { run, still } = usePlay(box)
  const [picked, setPicked] = useState({ index: 0, run: 0 })
  const [place, setPlace] = useState<Place | null>(null)
  const ask = ASKS[picked.index]
  // Each pick (and the first view) types its ask, then turns the globe.
  const turnKey = `${run}:${picked.run}`

  useEffect(() => {
    // Before the first view nothing is asked yet; the globe just turns.
    if (!still && run === 0 && picked.run === 0) return
    const timer = window.setTimeout(() => setPlace(ASKS[picked.index].place), still ? 0 : TYPED_MS)
    return () => window.clearTimeout(timer)
  }, [run, picked, still])

  return (
    <div ref={box} className="flex w-full flex-col items-center gap-4">
      <RotatingGlobe place={place} />
      <p key={turnKey} className="max-w-full rounded-full bg-highlight px-4 py-2 font-mono text-[13px]">
        {still ? ask.ask : <span className="type-in" style={{ '--chars': ask.ask.length } as CSSProperties}>{ask.ask}</span>}
      </p>
      <div role="group" aria-label="Ask for a place" className="flex flex-wrap justify-center gap-1.5">
        {ASKS.map((a, i) => (
          <button key={a.place.name} type="button" aria-pressed={i === picked.index}
                  onClick={() => setPicked((p) => ({ index: i, run: p.run + 1 }))}
                  className={`cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors ${
                    i === picked.index ? 'border-ink bg-ink text-paper' : 'border-line bg-panel text-muted hover:text-ink'}`}>
            {a.place.name}
          </button>
        ))}
      </div>
    </div>
  )
}

const POINTS = [
  {
    title: 'Read from your site',
    body: 'Your offices, your prices, your customers’ names. Lace works out your markets from what your pages already say.',
  },
  {
    title: 'Or just say where',
    body: '“Find me fintechs in Lisbon.” Name a place in chat and that search goes there, while everything else carries on as before.',
  },
  {
    title: 'Local, and current',
    body: 'It reads local news, sites and posts, recent first, and every find shows its source and date.',
  },
]

export function Worldwide() {
  return (
    <Section
      decor={
        // The globe's frame, turning far slower than the globe.
        <LaceSquare className="spin-glacial top-[30%] rotate-6 left-[10%] w-[80vw] lg:top-[30%] lg:left-[5%] lg:w-[min(34vw,30rem)]" />
      }
      title="It already knows where to look."
      intro={<>There’s no list of countries to pick from. <strong>Lace reads where you sell from your own website</strong>, and goes wherever you point it.</>}
    >
      <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <div data-reveal className="flex justify-center">
          <AskForAPlace />
        </div>
        <div className="flex flex-col gap-8">
          <div className="grid gap-5 sm:grid-cols-3">
            {POINTS.map((point, i) => (
              <div key={point.title} data-reveal style={stagger(i)}>
                <h3 className="font-semibold tracking-tight">{point.title}</h3>
                <p className="mt-1.5 leading-relaxed text-muted">{point.body}</p>
              </div>
            ))}
          </div>
          <div data-reveal style={stagger(3)}>
            <p className="font-mono text-xs uppercase tracking-wider text-brand-ink">Reasons to reach out it spots, anywhere</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {SIGNALS.map((signal) => (
                <li key={signal} className="rounded-full border border-brand/60 bg-highlight/50 px-2.5 py-1 font-mono text-[11px] tracking-wide text-ink">
                  {signal}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </Section>
  )
}
