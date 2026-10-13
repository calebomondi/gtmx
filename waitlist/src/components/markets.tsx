import type { ReactNode } from 'react'

import { stagger } from '../lib/stagger'
import { KenyaMotif, NigeriaMotif, SouthAfricaMotif } from './market-motifs'
import { Section } from './section'

const MARKETS: { country: string; code: string; note: string; motif: ReactNode }[] = [
  { country: 'Kenya', code: 'KE', note: 'SACCOs, county tenders and Nairobi’s startup scene.', motif: <KenyaMotif /> },
  { country: 'Nigeria', code: 'NG', note: 'Lagos distributors, manufacturers and a crowded fintech field.', motif: <NigeriaMotif /> },
  { country: 'South Africa', code: 'ZA', note: 'Enterprise procurement and the Joburg and Cape Town ecosystems.', motif: <SouthAfricaMotif /> },
]

export function Markets() {
  return (
    <Section
      label="Built for where you sell"
      title="Global sales tools know Silicon Valley. GTMX starts with Nairobi, Lagos and Joburg."
      intro="It researches local rivals, local buyers and local news: the tender, the new branch, the funding round that makes this the month to reach out."
    >
      <div className="grid gap-5 sm:grid-cols-3">
        {MARKETS.map((market, i) => (
          <article
            key={market.country}
            data-reveal
            style={stagger(i)}
            className="group relative overflow-hidden rounded-xl border border-line bg-panel transition duration-300 hover:-translate-y-1 hover:border-ink/20 hover:shadow-lift"
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
            <div className="p-6">
              <h3 className="text-xl font-semibold tracking-tight">{market.country}</h3>
              <p className="mt-2 leading-relaxed text-muted">{market.note}</p>
            </div>
          </article>
        ))}
      </div>
    </Section>
  )
}
