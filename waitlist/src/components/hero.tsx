import { SignupCard } from '../features/signup/signup-card'
import type { PilotSpots } from '../lib/api'
import { DEMO_VIDEO } from './demo-video'
import { DemoPlaceholder, ProductDemo } from './product-demo'

const PROOF = ['Kenya · Nigeria · South Africa', 'Four specialists on every run', 'You approve every send']

export function Hero({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  return (
    <section id="top" className="hero-paper flex min-h-[calc(100svh-3.5rem)] items-center">
      <div className="mx-auto grid w-full max-w-6xl gap-14 px-5 py-14 sm:px-8 lg:grid-cols-[1.08fr_1fr] lg:items-center lg:gap-16">
        <div className="flex min-w-0 flex-col gap-6">
          <p className="inline-flex w-fit items-center gap-2 rounded-full border border-ink/15 bg-panel/70 px-3 py-1 font-mono text-[11px] uppercase tracking-wider">
            <span aria-hidden className="size-1.5 rounded-full bg-brand" />
            For founders selling in Kenya, Nigeria &amp; South Africa
          </p>
          <h1 className="text-[2.75rem] leading-[1.02] font-semibold tracking-[-0.035em] text-balance sm:text-[4.1rem]">
            Know who to sell to, and <span className="marker whitespace-nowrap">why now.</span>
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-muted">
            GTMX is a go-to-market team you don’t have to hire. It studies your offer, maps your market and
            rivals, finds the companies and communities with a reason to buy this month, and drafts the first
            message. You approve every send.
          </p>
          <SignupCard id="join" pilot={pilot} onPilotSpotsLeft={onPilotSpotsLeft} />
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-[13px] text-muted">
            {PROOF.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <span aria-hidden className="size-2 rounded-[2px] bg-brand" />
                {item}
              </li>
            ))}
            {pilot && pilot.left > 0 && (
              <li className="flex items-center gap-2 font-medium text-ink">
                <span aria-hidden className="size-2 rounded-[2px] bg-ink" />
                {pilot.left} of {pilot.total} pilot spots open
              </li>
            )}
          </ul>
        </div>
        <div className="min-w-0 pr-3 pb-3 sm:pr-4 sm:pb-4">
          {DEMO_VIDEO ? <ProductDemo video={DEMO_VIDEO} /> : <DemoPlaceholder />}
        </div>
      </div>
    </section>
  )
}
