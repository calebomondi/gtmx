import { Section } from './section'

const STEPS = [
  { title: 'Tell it what you sell', body: 'Paste your website, or describe your product or service in a few sentences if you don’t have one.' },
  { title: 'Answer a few questions', body: 'Who it’s for, where you sell. A team of four specialists (product, market, competition and go-to-market) does the research.' },
  { title: 'Review, then send', body: 'Read the brief, pick the accounts, edit the drafts. Messages go from your own email, only when you click send.' },
]

export function HowItWorks() {
  return (
    <Section label="How it works" title="Three steps, and you stay in charge of every message.">
      <ol className="grid gap-8 sm:grid-cols-3">
        {STEPS.map((step, i) => (
          <li key={step.title} className="flex flex-col gap-3">
            <span className="font-mono text-sm text-brand-ink tabular-nums">0{i + 1}</span>
            <h3 className="text-lg font-semibold">{step.title}</h3>
            <p className="leading-relaxed text-muted">{step.body}</p>
          </li>
        ))}
      </ol>
    </Section>
  )
}
