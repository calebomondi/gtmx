import { useEffect, useState } from 'react'

import type { PilotSpots } from '../lib/api'
import { pilotStart } from '../lib/pilot-start'
import { stagger } from '../lib/stagger'
import { LaceSquare } from './lace-square'
import { Section } from './section'

// How long a newly taken dot pops before it settles.
const POP_MS = 1200

const GET = ['Your startup’s Lace, free for your whole founding team', 'A direct line to the team building it', 'A say in what Lace learns next']
const ASK = ['A 20-minute feedback call every two weeks', 'Honest answers about what works and what doesn’t']

// The dots drawn while the count loads: the size of a cohort, all open.
const LOADING_DOTS = 50

/** One dot per pilot spot, filled as they're taken. A spot taken while the
 * page is open pops in. */
function SpotDots({ pilot }: { pilot: PilotSpots | null }) {
  const total = pilot?.total ?? LOADING_DOTS
  const taken = pilot?.taken ?? 0
  // What was taken when the count was last seen: anything past it is new.
  const [seen, setSeen] = useState<number | null>(null)
  useEffect(() => {
    if (pilot === null) return
    const timer = window.setTimeout(() => setSeen(pilot.taken), POP_MS)
    return () => window.clearTimeout(timer)
  }, [pilot])
  return (
    <div
      data-dots
      role="img"
      aria-label={pilot ? `${taken} of ${total} pilot spots taken` : 'Pilot spots loading'}
      className={`grid w-fit grid-cols-10 gap-2 sm:gap-2.5 ${pilot ? '' : 'animate-pulse opacity-50'}`}
    >
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          style={stagger(i)}
          className={`size-3.5 rounded-[4px] border-2 border-ink sm:size-4 ${i < taken ? 'dot-taken' : 'bg-panel'} ${
            seen !== null && i >= seen && i < taken ? 'dot-new' : ''}`}
        />
      ))}
    </div>
  )
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl bg-panel p-6 shadow-lift">
      <h3 className="font-mono text-xs uppercase tracking-wider text-brand-ink">{title}</h3>
      <ul className="mt-4 flex flex-col gap-3">
        {items.map((item) => (
          <li key={item} className="flex gap-3 leading-snug">
            <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-[2px] bg-brand" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

function pilotTitle(pilot: PilotSpots | null): string {
  if (!pilot) return 'One spot per startup. Bring your founding team.'
  const { day, started } = pilotStart(pilot.starts_on)
  return started ? `${pilot.total} startups, running since ${day}.` : `${pilot.total} startups, starting ${day}.`
}

export function Pilot({ pilot }: { pilot: PilotSpots | null }) {
  const full = pilot !== null && pilot.left === 0
  return (
    <Section
      id="pilot"
      label="The pilot"
      title={pilotTitle(pilot)}
      intro="Join the waitlist and tick “Join the pilot”. We’ll email you to set up your Lace and book a short kickoff call."
    >
      <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div data-reveal className="relative isolate flex flex-col gap-6">
          {/* A pass: the count and its spots on one tilted square. */}
          <LaceSquare className="-top-8 -left-8 -z-10 w-[min(100%,26rem)] -rotate-3" />
          {pilot ? (
            <p className="flex flex-wrap items-end gap-x-4 gap-y-1">
              <span className="text-[6.5rem] leading-[0.8] font-semibold tracking-[-0.05em] tabular-nums sm:text-[9rem]">
                {pilot.left}
              </span>
              <span className="pb-2 text-lg font-medium sm:text-xl">
                of {pilot.total} pilot spots {full ? 'left: the pilot is full' : 'open'}
              </span>
            </p>
          ) : (
            <p className="text-3xl font-semibold">Limited pilot spots</p>
          )}
          <SpotDots pilot={pilot} />
          <a href="#join" className="btn-primary w-fit px-6 py-3.5">
            {full ? 'Join the waitlist' : 'Apply for the pilot'}
          </a>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <div data-reveal style={stagger(1)} className="relative isolate">
            {/* The page's one solid square: here is where you act. */}
            <LaceSquare className="-top-5 -right-5 -z-10 w-24 rotate-6 bg-brand sm:w-28" />
            <List title="What you get" items={GET} />
          </div>
          <div data-reveal style={stagger(2)}><List title="What we ask" items={ASK} /></div>
        </div>
      </div>
    </Section>
  )
}
