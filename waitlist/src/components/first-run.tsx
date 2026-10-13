import { Section } from './section'

const OUTPUTS = [
  {
    title: 'Your offer, in a buyer’s words',
    body: 'What you sell, the problem it solves and what sets it apart, written from your site or your own description.',
  },
  {
    title: 'Your market and who buys',
    body: 'Demand, pricing norms and the buyers who fit, country by country. For consumer offers: the communities, creators and events they follow.',
  },
  {
    title: 'Your rivals, watched',
    body: 'The companies your buyers compare you with, where each is weak, and alerts when they change pricing, launch or post.',
  },
  {
    title: 'Accounts with a reason to buy now',
    body: 'Companies and venues with a fresh trigger: a new depot, a funding round, a hiring spree. Each with who to contact and a drafted first message.',
  },
]

export function FirstRun() {
  return (
    <Section
      id="what-you-get"
      label="What your first run gives you"
      title="Four answers most founders spend months guessing at."
      intro="One run takes a few minutes. Everything it finds cites where it found it, so you can check it before you act on it."
    >
      <div className="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2">
        {OUTPUTS.map((output) => (
          <article key={output.title} className="bg-panel p-6 sm:p-8">
            <h3 className="text-lg font-semibold">{output.title}</h3>
            <p className="mt-2 leading-relaxed text-muted">{output.body}</p>
          </article>
        ))}
      </div>
    </Section>
  )
}
