import { SignupCard } from '../features/signup/signup-card'
import type { PilotSpots } from '../lib/api'
import { RunPreview } from './run-preview'

export function Hero({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  return (
    <section id="top" className="mx-auto grid max-w-6xl gap-12 px-5 pt-12 pb-16 sm:px-8 sm:pt-20 sm:pb-24 lg:grid-cols-[1.05fr_1fr] lg:items-start lg:gap-14">
      <div className="flex min-w-0 flex-col gap-7">
        <p className="font-mono text-xs uppercase tracking-wider text-muted">
          For founders selling in Kenya, Nigeria &amp; South Africa
        </p>
        <h1 className="text-[2.6rem] leading-[1.05] font-semibold tracking-tight text-balance sm:text-6xl">
          Know who to sell to, and{' '}
          <span className="bg-[linear-gradient(transparent_62%,var(--color-highlight)_62%)] px-0.5">why now.</span>
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-muted">
          GTMX is a go-to-market team you don’t have to hire. It studies your offer, maps your market and
          rivals, finds the companies and communities with a reason to buy this month, and drafts the first
          message. You approve every send.
        </p>
        <SignupCard pilot={pilot} onPilotSpotsLeft={onPilotSpotsLeft} />
        {pilot && pilot.left > 0 && (
          <p className="font-mono text-xs text-muted">
            Pilot: <span className="text-ink">{pilot.left} of {pilot.total}</span> spots open
          </p>
        )}
      </div>
      <div className="min-w-0">
        <RunPreview />
      </div>
    </section>
  )
}
