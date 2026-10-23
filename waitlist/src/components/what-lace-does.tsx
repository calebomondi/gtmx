import { stagger } from '../lib/stagger'
import { Lace, type LaceState } from './lace-mascot'
import { Section } from './section'

interface Column {
  title: string
  /** How the mascot looks over this column: finding, watching, working with you. */
  mood: LaceState
  items: { title: string; body: string }[]
}

const COLUMNS: Column[] = [
  {
    title: 'Finds',
    mood: 'thinking',
    items: [
      {
        title: 'Your ideal customers, and who to reach',
        body: 'Companies with a reason to buy now (a funding round, a new office, a hiring push) and the person there who decides.',
      },
      {
        title: 'Places to sell',
        body: 'Tenders, RFPs, procurement calls and public “looking for” posts that fit what you sell, with their deadlines.',
      },
      {
        title: 'Places to showcase and partner',
        body: 'Events, awards, podcasts and press to be seen at, and companies serving the same buyers to team up with.',
      },
    ],
  },
  {
    title: 'Watches',
    mood: 'alert',
    items: [
      {
        title: 'Your competitors',
        body: 'Who they are, where each is weak, and when one changes pricing, launches or posts something that matters.',
      },
      {
        title: 'Your replies',
        body: 'Answers on email and your social inboxes, read and sorted: interested, a question, wants to meet, not now.',
      },
      {
        title: 'What changed today',
        body: 'A daily brief in your Feed: new finds, competitor moves, replies waiting, and what to do next.',
      },
    ],
  },
  {
    title: 'Works with you',
    mood: 'idle',
    items: [
      {
        title: 'Brainstorms',
        body: 'Ask it anything about your market, your angle or a draft. It answers from what it knows about your startup.',
      },
      {
        title: 'Drafts your outreach',
        body: 'First messages in your voice on email, LinkedIn, X, Instagram, Facebook and TikTok, each built on why now.',
      },
      {
        title: 'Drafts your answers',
        body: 'When someone replies, the answer is waiting. You edit it, or ask Lace to, and send it with one click.',
      },
    ],
  },
]

export function WhatLaceDoes() {
  return (
    <Section
      id="what-lace-does"
      tone="white"
      label="What your Lace does"
      title="One assistant for everything between you and your next deal."
      intro="Your Lace works from what it knows about your startup and from the web as it is today. Everything it finds says where it found it, and waits for your OK before it is saved or sent."
    >
      <div className="grid gap-5 lg:grid-cols-3">
        {COLUMNS.map((column, c) => (
          <div key={column.title} data-reveal style={stagger(c)} className="flex flex-col rounded-xl border border-line bg-paper p-6 sm:p-7">
            <div className="flex items-center gap-3">
              <Lace state={column.mood} size={36} phase={c * 1.3} decorative />
              <h3 className="font-mono text-sm uppercase tracking-wider text-brand-ink">{column.title}</h3>
            </div>
            <ul className="mt-6 flex flex-col gap-5">
              {column.items.map((item) => (
                <li key={item.title} className="group border-l-2 border-brand/40 pl-4 transition-colors hover:border-brand">
                  <p className="font-semibold tracking-tight">{item.title}</p>
                  <p className="mt-1 leading-relaxed text-muted">{item.body}</p>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Section>
  )
}
