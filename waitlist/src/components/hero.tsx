import { SignupCard } from '../features/signup/signup-card'
import type { PilotSpots } from '../lib/api'
import { DEMO_VIDEO } from './demo-video'
import { Lace } from './lace-mascot'
import { LacePreview } from './lace-preview'
import { ProductDemo } from './product-demo'
import { RotatingWord } from './rotating-word'

const PROOF = ['One Lace per startup', 'Your cofounders on it too', 'Works wherever you sell', 'You approve every send']

// What Lace finds, one after another; read whole without motion.
const FINDS = ['leads.', 'opportunities.', 'partners.', 'next deal.']

export function Hero({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  return (
    <section id="top" className="hero-paper flex min-h-[calc(100svh-3.5rem)] items-center">
      <div className="mx-auto grid w-full max-w-7xl gap-14 px-5 py-14 sm:px-8 short:py-8 lg:grid-cols-[0.95fr_1.15fr] lg:items-center lg:gap-16">
        <div className="flex min-w-0 flex-col gap-6 short:gap-4">
          <div className="flex flex-col gap-3">
            <h1 className="text-[2.75rem] leading-[1.02] font-semibold tracking-[-0.035em] text-balance sm:text-[4.1rem] short:text-[2.6rem]">
              Meet{' '}
              {/* Lace itself, after its name, kept on one line with the comma; sized
                  to the letters, so it scales with them. */}
              <span className="whitespace-nowrap">
                Lace
                <Lace state="idle" size={64} decorative className="mx-[0.1em] inline-block size-[0.72em] align-baseline" />,
              </span>{' '}
              your startup’s assistant.
            </h1>
            <p className="text-2xl leading-tight font-semibold tracking-tight sm:text-3xl short:text-xl">
              It finds your{' '}
              <RotatingWord words={FINDS} whole="leads, opportunities, partners and your next deal." />
            </p>
          </div>
          <p className="max-w-xl text-lg leading-relaxed text-muted short:text-base">
            <span className="font-medium text-ink">One Lace for your startup, shared by your whole founding team.</span>{' '}
            Give it your website: it learns what you sell, finds leads that fit and who to reach there, spots places to
            sell, showcase and partner, watches competitors, brainstorms with you and drafts every message. Nothing goes
            out without your click.
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
          {DEMO_VIDEO ? <ProductDemo video={DEMO_VIDEO} /> : <LacePreview />}
        </div>
      </div>
    </section>
  )
}
