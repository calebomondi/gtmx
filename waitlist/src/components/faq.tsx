import { Section } from './section'

// Only what the page above doesn't already answer: the worries before signing up.
const QUESTIONS = [
  {
    q: 'Will it message people on its own?',
    a: 'No. Lace only drafts. Email and X messages go out from your own accounts when you click send; on LinkedIn, Instagram, Facebook and TikTok you copy the message and send it there yourself. Anyone who asks not to be contacted is never drafted to again.',
  },
  {
    q: 'We sell to consumers, not businesses. Does it still work?',
    a: 'Yes. Tell it who buys, and instead of companies it looks for where those people already gather: communities, creators, events and platforms, and who runs each one. What it drafts to them offers something for their audience, not a cold pitch.',
  },
  {
    q: 'What if it can’t find good matches?',
    a: 'It tells you, and asks a question that will sharpen the next search, instead of padding the list. Every find says why it fits and where it was found, and when you dismiss one you can say why, so the next search learns.',
  },
  {
    q: 'What happens to my data?',
    a: 'What your Lace learns stays in your account and is never shared with other users or used to work for anyone else. You can ask us to delete it at any time.',
  },
  {
    q: 'What will it cost?',
    a: 'The pilot is free. Pricing comes after the pilot, and pilot founders help us set it.',
  },
]

export function Faq() {
  return (
    <Section title="Before you ask." layout="split">
      <div className="faq border-t border-line">
        {QUESTIONS.map((item) => (
          <details key={item.q} className="group border-b border-line">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-6 rounded-md px-2 py-6 text-lg font-medium transition-colors hover:bg-paper sm:px-4 [&::-webkit-details-marker]:hidden">
              {item.q}
              <span
                aria-hidden
                className="grid size-8 shrink-0 place-items-center text-2xl leading-none font-light text-muted transition duration-300 group-open:rotate-45 group-open:text-brand-ink group-hover:text-ink"
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
