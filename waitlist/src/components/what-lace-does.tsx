import { useRef, type ComponentType } from 'react'

import { usePlay } from '../lib/motion'
import { stagger } from '../lib/stagger'
import { LaceSquare } from './lace-square'
import { Section } from './section'
import { DraftScene, FindsScene, WatchesScene, type SceneProps } from './what-lace-does-scenes'

interface Column {
  title: string
  /** Lace doing this column's job, in a few seconds. */
  Scene: ComponentType<SceneProps>
  items: { title: string; body: string }[]
}

const COLUMNS: Column[] = [
  {
    title: 'Finds',
    Scene: FindsScene,
    items: [
      {
        title: 'Leads worth reaching, and who to talk to',
        body: 'Selling to businesses: the ones with a reason to buy now (a funding round, a new office, a hiring push), and the person who signs off. Selling to people: the communities, creators and events where they already gather, and who runs them.',
      },
      {
        title: 'Places to sell',
        body: 'Whenever someone puts out a call for what you sell: tenders, RFPs, procurement notices and public “looking for” posts, with their deadlines.',
      },
      {
        title: 'Places to showcase and partner',
        body: 'Events, awards, podcasts and press where your customers are paying attention, and businesses that serve the same customers to team up with.',
      },
      {
        title: 'Funding you qualify for',
        body: 'Grants, incubators and accelerators with an open call that matches your sector, your stage and your country.',
      },
    ],
  },
  {
    title: 'Watches',
    Scene: WatchesScene,
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
    Scene: DraftScene,
    items: [
      {
        title: 'Brainstorms',
        body: 'Ask it anything about your market, your angle or a draft. It answers from what it knows about your startup.',
      },
      {
        title: 'Drafts your outreach, and your answers',
        body: 'First messages in your voice on email, LinkedIn, X, Instagram, Facebook and TikTok, each built on why now. When someone replies, the answer is waiting.',
      },
      {
        title: 'Learns from you',
        body: 'Correct what it got wrong, or say why a find doesn’t fit, and the next search steers clear. When nothing fits yet, it says so.',
      },
    ],
  },
]

/** A column's scene: it plays when the section comes into view, and again
 * when hovered or tapped. */
function Specimen({ Scene }: { Scene: ComponentType<SceneProps> }) {
  const box = useRef<HTMLDivElement>(null)
  const { run, still, replay } = usePlay(box)
  return (
    <div ref={box} aria-hidden onPointerEnter={replay} onClick={replay}
         className="h-40 overflow-hidden rounded-lg border border-line bg-panel p-4">
      <Scene key={run} still={still} />
    </div>
  )
}

export function WhatLaceDoes() {
  return (
    <Section
      id="what-lace-does"
      decor={<>
        {/* A chain, one square behind each column, each overlapping the next. */}
        <LaceSquare className="top-[20%] left-[-30%] w-[90vw] -rotate-6 lg:top-[34%] lg:left-[3%] lg:w-[min(34vw,30rem)]" />
        <LaceSquare className="top-[48%] right-[-30%] w-[90vw] rotate-3 lg:top-[42%] lg:right-auto lg:left-[33%] lg:w-[min(34vw,30rem)]" />
        <LaceSquare className="top-[76%] left-[-20%] w-[90vw] -rotate-2 lg:top-[34%] lg:left-[63%] lg:w-[min(34vw,30rem)]" />
      </>}
      title="Finds. Watches. Works with you."
      intro={<>One assistant for everything between you and your next deal, working from what it knows about your startup and the web as it is today. Everything it finds <strong>says where it found it, and waits for your OK</strong> before it is saved or sent.</>}
    >
      <div className="grid gap-5 lg:grid-cols-3">
        {COLUMNS.map((column, c) => (
          <div key={column.title} data-reveal style={stagger(c)} className="flex flex-col rounded-xl border border-line bg-paper/60 p-6 sm:p-7">
            <Specimen Scene={column.Scene} />
            <h3 className="mt-6 text-lg font-semibold tracking-tight">{column.title}</h3>
            <ul className="mt-4 flex flex-col gap-5">
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
