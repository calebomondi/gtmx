import { stagger } from '../lib/stagger'
import { Section } from './section'

const QUESTIONS = [
  {
    q: 'Will it email people on its own?',
    a: 'No. GTMX drafts messages; you read, edit and send them from your own email. Nothing goes out without your click, and anyone who asks not to be contacted is never drafted to again.',
  },
  {
    q: 'What if I don’t have a website?',
    a: 'Describe what you sell in a few sentences. That’s enough for a first run, and you can add more later.',
  },
  {
    q: 'Does it work for consumer products?',
    a: 'Yes. For consumer offers it looks for the communities, creators and events your buyers follow, and pitches them a partnership rather than a sale.',
  },
  {
    q: 'What happens to my data?',
    a: 'Your research stays in your workspace and is never shared with other users. We follow Kenya’s Data Protection Act, Nigeria’s NDPR and South Africa’s POPIA, and you can ask us to delete your data at any time.',
  },
  {
    q: 'What will it cost?',
    a: 'The pilot is free. Pricing comes after the pilot, and pilot founders help us set it.',
  },
]

export function Faq() {
  return (
    <Section tone="white" label="Questions" title="Before you ask.">
      <div className="faq border-t border-line">
        {QUESTIONS.map((item, i) => (
          <details key={item.q} data-reveal style={stagger(i)} className="group border-b border-line">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-6 rounded-md px-2 py-6 text-lg font-medium transition-colors hover:bg-paper sm:px-4 [&::-webkit-details-marker]:hidden">
              {item.q}
              <span
                aria-hidden
                className="grid size-8 shrink-0 place-items-center rounded-full border border-line font-mono text-lg transition duration-300 group-open:rotate-45 group-open:border-brand group-open:bg-brand group-hover:border-brand"
              >
                +
              </span>
            </summary>
            <p className="max-w-3xl px-2 pb-6 leading-relaxed text-muted sm:px-4">{item.a}</p>
          </details>
        ))}
      </div>
    </Section>
  )
}
