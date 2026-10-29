import { SignupCard } from '../features/signup/signup-card'
import type { PilotSpots } from '../lib/api'
import { stagger } from '../lib/stagger'
import { BrandMark } from './brand-mark'
import { FooterWordmark } from './footer-wordmark'
import { Lace } from './lace-mascot'

const X_URL = 'https://x.com/thalaceai'

/** The last word: a full-width black block with the signup inline, Lace on top. */
export function Closing({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  return (
    <footer className="on-dark overflow-hidden bg-night text-paper">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 pt-20 pb-12 sm:px-8 sm:pt-28 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div data-reveal className="flex flex-col gap-5">
          <h2 className="text-[2.5rem] leading-[1.02] font-semibold tracking-[-0.035em] text-balance sm:text-6xl">
            Your next lead, partner or deal is out there. <span className="text-brand">Your Lace finds it.</span>
          </h2>
          <p className="max-w-md text-lg leading-relaxed text-night-muted">
            One email puts you on the list. Tick the pilot on the next step if you want your Lace early.
          </p>
        </div>
        <div data-reveal style={stagger(1)} className="relative">
          {/* Lace peeks over the signup, waiting for you. */}
          <Lace state="alert" size={64} decorative className="absolute -top-10 right-8 z-10 drop-shadow-lg" />
          <div className="rounded-2xl bg-paper p-5 text-ink shadow-[0_0_0_6px_var(--color-brand)] sm:p-7">
            <SignupCard pilot={pilot} onPilotSpotsLeft={onPilotSpotsLeft} />
          </div>
        </div>
      </div>
      <div className="mx-auto flex max-w-7xl flex-col gap-3 border-t border-night-line px-5 py-8 text-sm text-night-muted sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <BrandMark className="text-paper" />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
          <p>An assistant for every startup, wherever it sells.</p>
          <a href={X_URL} target="_blank" rel="noreferrer" aria-label="Thalace on X (@thalaceai)" className="flex w-fit items-center gap-2 text-paper hover:text-brand">
            <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="currentColor">
              <path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z" />
            </svg>
            @thalaceai
          </a>
        </div>
      </div>
      <FooterWordmark />
    </footer>
  )
}
