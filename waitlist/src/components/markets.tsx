import { Section } from './section'

const MARKETS = [
  { country: 'Kenya', note: 'SACCOs, county tenders and Nairobi’s startup scene.' },
  { country: 'Nigeria', note: 'Lagos distributors, manufacturers and a crowded fintech field.' },
  { country: 'South Africa', note: 'Enterprise procurement and the Joburg and Cape Town ecosystems.' },
]

export function Markets() {
  return (
    <Section
      label="Built for where you sell"
      title="Global sales tools know Silicon Valley. GTMX starts with Nairobi, Lagos and Joburg."
      intro="It researches local rivals, local buyers and local news: the tender, the new branch, the funding round that makes this the month to reach out."
    >
      <div className="grid gap-4 sm:grid-cols-3">
        {MARKETS.map((market) => (
          <div key={market.country} className="rounded-xl border border-line bg-panel p-6">
            <h3 className="text-lg font-semibold">{market.country}</h3>
            <p className="mt-2 leading-relaxed text-muted">{market.note}</p>
          </div>
        ))}
      </div>
    </Section>
  )
}
