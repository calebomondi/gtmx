import { stagger } from '../lib/stagger'
import { Section } from './section'

const QUESTIONS = [
  {
    q: 'What is a Lace?',
    a: 'Your startup’s own AI assistant. You name it and give it your website; it learns what you sell, and from then on finds leads, opportunities and partners, watches your competitors, and drafts your messages and replies. You talk to it in a chat, and see what it did in your Feed and Messaging.',
  },
  {
    q: 'Will it message people on its own?',
    a: 'No. Lace only drafts. Email and X messages go out from your own accounts when you click send; on LinkedIn, Instagram, Facebook and TikTok you copy the message and send it there yourself. Anyone who asks not to be contacted is never drafted to again.',
  },
  {
    q: 'Can it find more than leads?',
    a: 'Yes. Besides leads, it looks for places to sell (tenders, RFPs, procurement calls), places to be seen (events, awards, podcasts, press), partners who serve the same customers, and grants, incubators and accelerators you qualify for, each with its deadline and why it fits.',
  },
  {
    q: 'We sell to consumers, not businesses. Does it still work?',
    a: 'Yes. Tell it who buys, and instead of companies it looks for where those people already gather: communities, creators, events and platforms, and who runs each one. What it drafts to them offers something for their audience, not a cold pitch.',
  },
  {
    q: 'Does it work in my country?',
    a: 'It works wherever you sell. Tell it the countries, and it researches buyers, rivals and news there.',
  },
  {
    q: 'Why one Lace per startup?',
    a: 'So your startup has one memory: what you sell, who buys, every competitor, every conversation and draft. Everyone on the team works from it, and nothing is learned twice. If you run more than one startup, each gets its own Lace.',
  },
  {
    q: 'Can my cofounders use it too?',
    a: 'Yes. Invite them by email to your Lace. You all share one team chat (it shows who asked what), one Feed and one Messaging, and you can talk to Lace at the same time: messages wait their turn, and searches keep running while you chat.',
  },
  {
    q: 'Can we each talk to it privately?',
    a: 'Yes. Each of you has a “Just you” chat next to the team chat. What Lace finds there stays yours until you push it to the team, with a note, and a cofounder approves it.',
  },
  {
    q: 'Which tools does it connect to?',
    a: 'Gmail and Outlook, LinkedIn, X, Instagram, Facebook, TikTok and Telegram for reaching people; HubSpot and Zoho CRM; Google Sheets and Notion; Slack and Asana; Google Calendar and Calendly. WhatsApp is coming. Anything Lace would do in them, it proposes first, and it runs only when you approve.',
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
    <Section tone="notes" label="Questions" title="Before you ask.">
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
