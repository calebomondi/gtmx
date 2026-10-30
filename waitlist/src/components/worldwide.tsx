import { stagger } from '../lib/stagger'
import { RotatingGlobe } from './rotating-globe'
import { Section } from './section'

/** Reasons to reach out now, the kind Lace spots wherever you sell. */
const SIGNALS = [
  'funding rounds', 'new offices', 'tenders & RFPs', 'hiring pushes', 'product launches',
  'leadership moves', 'conferences', 'partnerships', 'growing communities', 'tool switches',
]

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
      title="It already knows where to look."
      intro="There’s no list of countries to pick from. Lace reads where you sell from your own website, and goes wherever you point it."
    >
      <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <div data-reveal className="flex justify-center">
          <RotatingGlobe />
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
