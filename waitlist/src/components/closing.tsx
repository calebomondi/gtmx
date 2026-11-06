import { useEffect, useRef, type RefObject } from 'react'

import { SignupCard } from '../features/signup/signup-card'
import type { PilotSpots } from '../lib/api'
import { useLookAtPointer } from '../lib/use-look-at-pointer'
import { useScrollScenes, watchPassage } from '../lib/use-scroll-progress'
import { BrandMark } from './brand-mark'
import { FooterWordmark } from './footer-wordmark'
import { Lace } from './lace-mascot'

const X_URL = 'https://x.com/thalaceai'
const TELEGRAM_URL = 'https://t.me/thalaceai'

/** The last word: a full-width black block with the signup inline, Lace on top. */
/** How far below the card's edge Lace waits, hidden, before it rises. */
const HIDDEN_PX = 64

/** Lace rises from behind the signup card as the page reaches the end, and
 * sinks back as you scroll up. Without motion it simply sits there. */
function usePeek(card: RefObject<HTMLDivElement | null>, lace: RefObject<HTMLSpanElement | null>) {
  const on = useScrollScenes(0)
  useEffect(() => {
    const box = card.current
    const el = lace.current
    if (!box || !el) return
    if (!on) {
      el.removeAttribute('style')
      return
    }
    return watchPassage(box, (p) => {
      el.style.transform = `translateY(${(1 - p) * HIDDEN_PX}px)`
    }, 0.95, 0.6)
  }, [card, lace, on])
}

export function Closing({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  const card = useRef<HTMLDivElement>(null)
  const lace = useRef<HTMLSpanElement>(null)
  const look = useLookAtPointer(lace)
  usePeek(card, lace)
  return (
    <footer className="on-dark overflow-hidden bg-night text-paper">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 pt-20 pb-12 sm:px-8 sm:pt-28 lg:grid-cols-[1.1fr_1fr] lg:items-center">
        <div className="flex flex-col gap-5">
          <h2 className="text-[2.5rem] leading-[1.02] font-semibold tracking-[-0.035em] text-balance sm:text-6xl">
            Your next lead, partner or deal is out there. <span className="text-brand">Your Lace finds it.</span>
          </h2>
          <p className="max-w-md text-lg leading-relaxed text-night-muted">
            One email puts you on the list. Tick the pilot on the next step if you want your Lace early.
          </p>
        </div>
        <div ref={card} className="relative isolate">
          {/* Lace peeks over the signup from behind it, watching your cursor. */}
          <span ref={lace} className="absolute -top-10 right-8 -z-10 block will-change-transform">
            <Lace state="alert" size={64} look={look} decorative className="drop-shadow-lg" />
          </span>
          <div className="rounded-2xl bg-paper p-5 text-ink shadow-[0_0_0_6px_var(--color-brand)] sm:p-7">
            <SignupCard pilot={pilot} onPilotSpotsLeft={onPilotSpotsLeft} />
          </div>
        </div>
      </div>
      <div className="mx-auto flex max-w-7xl flex-col gap-3 border-t border-night-line px-5 py-8 text-sm text-night-muted sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <BrandMark className="text-paper" />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
          <p>An assistant for every startup, wherever it sells.</p>
          <div className="flex items-center gap-5">
            <a href={X_URL} target="_blank" rel="noreferrer" aria-label="Thalace on X (@thalaceai)" className="flex w-fit items-center gap-2 text-paper hover:text-brand">
              <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="currentColor">
                <path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z" />
              </svg>
              @thalaceai
            </a>
            <a href={TELEGRAM_URL} target="_blank" rel="noreferrer" aria-label="Thalace's Telegram group" className="flex w-fit items-center gap-2 text-paper hover:text-brand">
              <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="currentColor">
                <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
              </svg>
              Telegram
            </a>
          </div>
        </div>
      </div>
      <FooterWordmark />
    </footer>
  )
}
