import type { ReactNode } from 'react'

import { stagger } from '../lib/stagger'
import { KenyaMotif, NigeriaMotif, SouthAfricaMotif } from './market-motifs'
import { Section } from './section'

interface Market {
  country: string
  code: string
  hook: string
  body: string
  /** Buying signals GTMX watches for in this market. */
  signals: string[]
  motif: ReactNode
}

const MARKETS: Market[] = [
  {
    country: 'Kenya',
    code: 'KE',
    hook: 'Sell into Nairobi’s fastest movers.',
    body: 'GTMX tracks Kenyan startups and SMEs as they raise, hire and open new branches. You reach them in the week they’re ready to buy, not the quarter after.',
    signals: ['funding rounds', 'new branches', 'key hires'],
    motif: <KenyaMotif />,
  },
  {
    country: 'Nigeria',
    code: 'NG',
    hook: 'Cut through Lagos’ crowded market.',
    body: 'Distributors, manufacturers and fintechs in Nigeria buy fast when something changes. GTMX spots the expansion, the launch or the new leader, and drafts the message that lands.',
    signals: ['expansions', 'product launches', 'leadership moves'],
    motif: <NigeriaMotif />,
  },
  {
    country: 'South Africa',
    code: 'ZA',
    hook: 'Get in front of Joburg and Cape Town buyers early.',
    body: 'South African scale-ups and mid-sized firms move on clear signals. GTMX finds the companies hiring, growing and switching tools, and the person who decides.',
    signals: ['hiring sprees', 'new offices', 'tool switches'],
    motif: <SouthAfricaMotif />,
  },
]

export function Markets() {
  return (
    <Section
      label="Built for where you sell"
      title="Global sales tools know Silicon Valley. GTMX starts with Nairobi, Lagos and Joburg."
      intro="It researches local rivals, local buyers and local news: the key hire, the new branch, the funding round that makes this the month to reach out."
    >
      <div className="grid gap-5 sm:grid-cols-3">
        {MARKETS.map((market, i) => (
          <article
            key={market.country}
            data-reveal
            style={stagger(i)}
            className="group relative flex flex-col overflow-hidden rounded-xl border border-line bg-panel transition duration-300 hover:-translate-y-1 hover:border-ink/20 hover:shadow-lift"
          >
            <div className="relative h-32 overflow-hidden bg-highlight/60 px-5 pt-6 text-brand-deep">
              <div className="h-full transition-transform duration-500 group-hover:scale-[1.04] group-hover:-translate-y-0.5">
                {market.motif}
              </div>
              <span
                aria-hidden
                className="absolute top-3 right-4 font-mono text-4xl font-semibold tracking-tight text-ink/10"
              >
                {market.code}
              </span>
            </div>
            {/* Grows to fill the card, so the chips sit on one line across all three. */}
            <div className="flex flex-1 flex-col p-6">
              <h3 className="text-xl font-semibold tracking-tight">{market.country}</h3>
              <p className="mt-2 font-semibold leading-snug text-balance">{market.hook}</p>
              <p className="mt-2 leading-relaxed text-muted">{market.body}</p>
              <ul className="mt-auto flex flex-wrap gap-2 pt-5" aria-label={`Signals GTMX watches in ${market.country}`}>
                {market.signals.map((signal) => (
                  <li
                    key={signal}
                    className="rounded-full border border-brand/60 bg-highlight/50 px-2.5 py-1 font-mono text-[11px] tracking-wide text-ink"
                  >
                    {signal}
                  </li>
                ))}
              </ul>
            </div>
          </article>
        ))}
      </div>
    </Section>
  )
}
