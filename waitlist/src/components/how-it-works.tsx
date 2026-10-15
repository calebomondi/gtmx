import { stagger } from '../lib/stagger'
import { Section } from './section'

const STEPS = [
  { title: 'Tell it what you sell', body: 'Paste your website, or describe your product or service in a few sentences if you don’t have one.' },
  { title: 'Answer a few questions', body: 'Who it’s for, where you sell. A team of four specialists (product, market, competition and go-to-market) does the research.' },
  { title: 'Review, then send', body: 'Read the brief, pick the accounts, edit the drafts. Messages go from your own email, only when you click send.' },
]

/** A timeline: orange nodes on a line that draws itself, across on wide
 * screens and down on phones. */
export function HowItWorks() {
  return (
    <Section tone="night" label="How it works" title="Three steps, and you stay in charge of every message.">
      <ol className="relative grid gap-12 pl-10 sm:grid-cols-3 sm:gap-10 sm:pl-0 sm:pt-14">
        <span aria-hidden data-draw="y" className="absolute top-2 bottom-2 left-[11px] w-px bg-brand/60 sm:hidden" />
        <span aria-hidden data-draw className="absolute top-[11px] right-[16%] left-[11px] hidden h-px bg-brand/60 sm:block" />
        {STEPS.map((step, i) => (
          <li key={step.title} data-reveal style={stagger(i + 1)} className="relative flex flex-col gap-3">
            <span
              aria-hidden
              className="absolute top-0.5 -left-10 grid size-6 place-items-center rounded-full bg-brand font-mono text-[11px] font-semibold text-ink ring-8 ring-night sm:-top-14 sm:left-0"
            >
              {i + 1}
            </span>
            <h3 className="text-xl font-semibold tracking-tight">{step.title}</h3>
            <p className="leading-relaxed text-night-muted">{step.body}</p>
          </li>
        ))}
      </ol>
    </Section>
  )
}
