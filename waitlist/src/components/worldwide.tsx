import { stagger } from '../lib/stagger'
import { Section } from './section'

/** Reasons to reach out now, the kind Lace watches for wherever you sell. */
const SIGNALS = [
  'funding rounds', 'new offices', 'tenders & RFPs', 'hiring pushes', 'product launches',
  'leadership moves', 'conferences', 'partnerships', 'expansions', 'tool switches',
]

const POINTS = [
  { title: 'Where your buyers are', body: 'Tell it the countries you sell in. It looks for buyers, rivals and news there, not in a default market.' },
  { title: 'In their language', body: 'It reads local sites, news and posts in the language they are written in, and drafts in the one you choose.' },
  { title: 'As of today', body: 'Searches favour what is recent, and every find shows its source and date, so stale news never passes for a reason.' },
]

// Finds blinking on the globe, as (x, y) in its 200×200 box.
const FINDS = [[62, 70], [128, 58], [104, 104], [150, 118], [74, 132], [118, 150]]

/** A line globe: meridians and parallels, with finds blinking on it. */
function Globe() {
  return (
    <svg viewBox="0 0 200 200" className="h-auto w-full max-w-sm text-brand-deep" aria-hidden>
      <circle cx="100" cy="100" r="88" fill="var(--color-highlight)" fillOpacity="0.45" stroke="currentColor" strokeWidth="1.2" />
      {[22, 48, 70].map((rx) => (
        <ellipse key={rx} cx="100" cy="100" rx={rx} ry="88" fill="none" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1" />
      ))}
      <line x1="100" y1="12" x2="100" y2="188" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1" />
      {[-56, -28, 0, 28, 56].map((dy) => {
        const half = Math.sqrt(88 * 88 - dy * dy)
        return <line key={dy} x1={100 - half} y1={100 + dy} x2={100 + half} y2={100 + dy} stroke="currentColor" strokeOpacity="0.45" strokeWidth="1" />
      })}
      {FINDS.map(([x, y], i) => (
        <g key={`${x}-${y}`}>
          <circle cx={x} cy={y} r="9" fill="var(--color-brand)" className="find-pulse" style={{ animationDelay: `${i * 0.6}s` }} />
          <rect x={x - 4} y={y - 4} width="8" height="8" rx="1.5" fill="var(--color-ink)" />
        </g>
      ))}
    </svg>
  )
}

export function Worldwide() {
  return (
    <Section
      label="Works wherever you sell"
      title="Your market is wherever your buyers are."
      intro="Lace isn’t tuned to one country. It researches the markets you name, the way someone local would: local rivals, local buyers, local news."
    >
      <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <div data-reveal className="flex justify-center"><Globe /></div>
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
            <p className="font-mono text-xs uppercase tracking-wider text-brand-ink">Reasons to reach out it watches for</p>
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
