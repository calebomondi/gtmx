import { useCallback, useState } from 'react'

import { stagger } from '../lib/stagger'
import { RotatingGlobe } from './rotating-globe'
import { Section } from './section'

/** Reasons to reach out now, the kind Lace spots wherever you sell. */
const SIGNALS = [
  'funding rounds', 'new offices', 'tenders & RFPs', 'hiring pushes', 'product launches',
  'leadership moves', 'conferences', 'partnerships', 'expansions', 'tool switches',
]

const POINTS = [
  {
    title: 'Read from your site',
    body: 'Your offices, your currencies, your customers’ logos. Lace works out your markets from what your pages already say.',
  },
  {
    title: 'Or just say where',
    body: '“Find me clinics in Lisbon.” Name a place in chat and that search goes there, while everything else carries on as before.',
  },
  {
    title: 'Local, and current',
    body: 'It reads local news, sites and posts in their own language, recent first, and every find shows its source and date.',
  },
]

/** What a Lace might be finding under the part of the world facing you, by
 * the longitude it sits at. Invented examples. */
const REGIONS = [
  { lon: -100, text: 'Over North America: a Toronto fintech is hiring its first head of partnerships.' },
  { lon: -55, text: 'Over South America: a São Paulo retailer just opened an office in Bogotá.' },
  { lon: 0, text: 'Over Europe: a Berlin logistics firm just raised its Series A.' },
  { lon: 35, text: 'Over Africa: a Nairobi tender for clinic software closes in 12 days.' },
  { lon: 78, text: 'Over South Asia: a Bengaluru SaaS company is looking for reseller partners.' },
  { lon: 115, text: 'Over East Asia: a Singapore summit has opened its call for speakers.' },
  { lon: 150, text: 'Over Oceania: a Sydney clinic group is opening three new sites.' },
]

function nearestRegion(lon: number): number {
  const gap = (a: number) => Math.abs(((lon - a + 540) % 360) - 180)
  return REGIONS.reduce((best, region, i) => (gap(region.lon) < gap(REGIONS[best].lon) ? i : best), 0)
}

export function Worldwide() {
  const [region, setRegion] = useState(() => nearestRegion(-20))
  // Called every frame; the state only changes when another region faces you.
  const onFacing = useCallback((lon: number) => setRegion(nearestRegion(lon)), [])

  return (
    <Section
      label="Works wherever you sell"
      title="It already knows where to look."
      intro="There’s no list of countries to pick from. Lace reads where you sell from your own website, and goes wherever you point it."
    >
      <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <div data-reveal className="flex flex-col items-center gap-4">
          <RotatingGlobe onFacing={onFacing} />
          <p className="min-h-10 max-w-sm text-center text-sm" aria-live="off">
            <span key={region} className="word-in inline-block">{REGIONS[region].text}</span>
          </p>
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
