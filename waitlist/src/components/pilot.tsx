import type { PilotSpots } from '../lib/api'
import { Section } from './section'

const GET = [
  'GTMX free for the whole pilot',
  'A direct line to the team building it',
  'A say in what we build next',
]

const ASK = ['A 20-minute feedback call every two weeks', 'Honest answers about what works and what doesn’t']

export function Pilot({ pilot }: { pilot: PilotSpots | null }) {
  const full = pilot !== null && pilot.left === 0
  return (
    <Section
      id="pilot"
      label="The pilot"
      title={pilot ? `${pilot.total} founders, starting in two weeks.` : 'A small group of founders, starting in two weeks.'}
      intro="Join the waitlist and tick “Join the pilot”. We’ll email pilots within two weeks of signing up to set up an account and a short kickoff call."
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr_auto]">
        <div className="rounded-xl border border-line bg-panel p-6">
          <h3 className="font-semibold">What you get</h3>
          <ul className="mt-3 flex flex-col gap-2 text-muted">
            {GET.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div className="rounded-xl border border-line bg-panel p-6">
          <h3 className="font-semibold">What we ask</h3>
          <ul className="mt-3 flex flex-col gap-2 text-muted">
            {ASK.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div className="flex flex-col justify-between gap-4 rounded-xl border border-brand bg-highlight/50 p-6 lg:w-60">
          {pilot ? (
            <p>
              <span className="block text-4xl font-semibold tabular-nums">{pilot.left}</span>
              <span className="text-sm text-muted">of {pilot.total} pilot spots {full ? 'left: the pilot is full' : 'open'}</span>
            </p>
          ) : (
            <p className="text-sm text-muted">Limited pilot spots.</p>
          )}
          <a href="#join" className="rounded-md bg-ink px-4 py-2.5 text-center text-sm font-semibold text-paper hover:bg-ink/85">
            {full ? 'Join the waitlist' : 'Apply for the pilot'}
          </a>
        </div>
      </div>
    </Section>
  )
}
