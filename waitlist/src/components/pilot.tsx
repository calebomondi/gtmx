import type { PilotSpots } from '../lib/api'
import { pilotStart } from '../lib/pilot-start'
import { stagger } from '../lib/stagger'
import { Section } from './section'

const GET = ['Your startup’s Lace, free for your whole founding team', 'A direct line to the team building it', 'A say in what Lace learns next']
const ASK = ['A 20-minute feedback call every two weeks', 'Honest answers about what works and what doesn’t']

function SpotDots({ pilot }: { pilot: PilotSpots }) {
  return (
    <div
      data-dots
      role="img"
      aria-label={`${pilot.taken} of ${pilot.total} pilot spots taken`}
      className="grid w-fit grid-cols-10 gap-2 sm:gap-2.5"
    >
      {Array.from({ length: pilot.total }, (_, i) => (
        <span
          key={i}
          style={stagger(i)}
          className={`size-3.5 rounded-full border-2 border-ink sm:size-4 ${i < pilot.taken ? 'dot-taken' : 'bg-panel'}`}
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
      tone="brand"
      label="The pilot"
      title={pilotTitle(pilot)}
      intro="One spot per startup, and your whole founding team comes with it. Join the waitlist and tick “Join the pilot”; we’ll email you to set up your Lace and a short kickoff call."
    >
      <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div data-reveal className="flex flex-col gap-6">
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
          {pilot && <SpotDots pilot={pilot} />}
          <a href="#join" className="btn-primary w-fit px-6 py-3.5 hover:bg-panel">
            {full ? 'Join the waitlist' : 'Apply for the pilot'}
          </a>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <div data-reveal style={stagger(1)}><List title="What you get" items={GET} /></div>
          <div data-reveal style={stagger(2)}><List title="What we ask" items={ASK} /></div>
        </div>
      </div>
    </Section>
  )
}
