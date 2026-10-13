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
    <Section label="Questions" title="Before you ask.">
      <div className="divide-y divide-line border-y border-line">
        {QUESTIONS.map((item) => (
          <details key={item.q} className="group py-5">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-lg font-medium">
              {item.q}
              <span aria-hidden className="font-mono text-muted transition group-open:rotate-45">+</span>
            </summary>
            <p className="mt-3 max-w-3xl leading-relaxed text-muted">{item.a}</p>
          </details>
        ))}
      </div>
    </Section>
  )
}
