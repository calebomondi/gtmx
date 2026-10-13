import { SignupCard } from '../features/signup/signup-card'
import type { PilotSpots } from '../lib/api'
import { stagger } from '../lib/stagger'
import { BrandMark } from './brand-mark'
import { FooterWordmark } from './footer-wordmark'

/** The last word: a full-width black block with the signup inline. */
export function Closing({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  return (
    <footer className="on-dark overflow-hidden bg-night text-paper">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 pt-20 pb-12 sm:px-8 sm:pt-28 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div data-reveal className="flex flex-col gap-5">
          <p className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-brand">
            <span aria-hidden className="h-px w-6 bg-brand" />
            Join the waitlist
          </p>
          <h2 className="text-[2.5rem] leading-[1.02] font-semibold tracking-[-0.035em] text-balance sm:text-6xl">
            Stop guessing <span className="text-brand">who to sell to.</span>
          </h2>
          <p className="max-w-md text-lg leading-relaxed text-night-muted">
            One email puts you on the list. Tick the pilot on the next step if you want in early.
          </p>
        </div>
        <div data-reveal style={stagger(1)} className="rounded-2xl bg-paper p-5 text-ink shadow-[0_0_0_6px_var(--color-brand)] sm:p-7">
          <SignupCard pilot={pilot} onPilotSpotsLeft={onPilotSpotsLeft} />
        </div>
      </div>
      <div className="mx-auto flex max-w-7xl flex-col gap-3 border-t border-night-line px-5 py-8 text-sm text-night-muted sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <BrandMark className="text-paper" />
        <p>For founders selling across Africa.</p>
      </div>
      <FooterWordmark />
    </footer>
  )
}
