import { useEffect, useState } from 'react'

import type { PilotSpots } from '../lib/api'
import { pilotStart } from '../lib/pilot-start'
import { stagger } from '../lib/stagger'
import { Section } from './section'

// How long a newly taken dot pops before it settles.
const POP_MS = 1200

const GET = ['Your startup’s Lace, free for your whole founding team', 'A direct line to the team building it', 'A say in what Lace learns next']
const ASK = [
  'Your feedback and suggestions as you use it: the feedback button in the app, or a reply to our emails',
  'Honest answers about what works and what doesn’t',
]

// The spots drawn while the count loads: the size of a cohort, all open.
const LOADING_SPOTS = 50

/** The pilot as Laces: one square per spot. A taken spot is a startup's
 * Lace, eyes open; an open one is an empty outline. Taken spots light up
 * once the section is in view, and one taken while the page is open pops in. */
function SpotLaces({ pilot }: { pilot: PilotSpots | null }) {
  const total = pilot?.total ?? LOADING_SPOTS
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
      className={`grid w-fit grid-cols-10 gap-1.5 sm:gap-2 ${pilot ? '' : 'animate-pulse opacity-50'}`}
    >
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          style={stagger(i)}
          className={`spot ${i < taken ? 'dot-taken' : ''} ${seen !== null && i >= seen && i < taken ? 'dot-new' : ''}`}
        >
          {i < taken && <><span className="spot-eye left-[22%]" /><span className="spot-eye right-[22%]" /></>}
        </span>
      ))}
    </div>
  )
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="border-t border-line pt-5">
      <h3 className="font-sans text-[15px] font-semibold">{title}</h3>
      <ul className="mt-3 flex flex-col gap-2.5 text-muted">
        {items.map((item) => <li key={item} className="leading-snug">{item}</li>)}
      </ul>
    </div>
  )
}

function pilotTitle(pilot: PilotSpots | null): string {
  if (!pilot) return 'One spot per startup. Bring your founding team.'
  const { day, started } = pilotStart(pilot.starts_on)
  return started ? `${pilot.total} startups, running since ${day}.` : `${pilot.total} startups, starting ${day}.`
}

/** Where the cohort stands, said in words beside the squares. */
function SpotCount({ pilot }: { pilot: PilotSpots | null }) {
  if (!pilot) return <p className="font-display text-3xl font-semibold tracking-tight">Limited pilot spots.</p>
  const lead = pilot.taken === 1 ? '1 startup has its Lace.' : `${pilot.taken} startups have their Lace.`
  return (
    <p className="font-display text-3xl leading-tight font-semibold tracking-[-0.02em] text-balance sm:text-4xl">
      {pilot.taken > 0 && <>{lead} </>}
      <span className="text-muted">
        {pilot.left === 0 ? 'The pilot is full.' : pilot.left === 1 ? 'One spot left.' : `${pilot.left} spots left.`}
      </span>
    </p>
  )
}

export function Pilot({ pilot }: { pilot: PilotSpots | null }) {
  const full = pilot !== null && pilot.left === 0
  return (
    <Section
      id="pilot"
      title={pilotTitle(pilot)}
      intro="Join the waitlist and tick “Join the pilot”. We’ll email you to set up your Lace."
    >
      <div className="grid gap-12 lg:grid-cols-[auto_1fr] lg:items-start lg:gap-16">
        <SpotLaces pilot={pilot} />
        <div className="flex max-w-xl flex-col gap-8">
          <SpotCount pilot={pilot} />
          <a href="#join" className="btn-primary w-fit px-6 py-3.5">
            {full ? 'Join the waitlist' : 'Apply for the pilot'}
          </a>
          <div className="grid gap-6 sm:grid-cols-2">
            <List title="What you get" items={GET} />
            <List title="What we ask" items={ASK} />
          </div>
        </div>
      </div>
    </Section>
  )
}
