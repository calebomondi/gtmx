import { useRef, type CSSProperties } from 'react'

import { usePlay } from '../lib/motion'
import { DemoFrame } from './demo-frame'

// What the screenshot shows, pointed at where it is: shares of the wide
// image, which is the one shown from sm up. The phone crop gets none.
const CALLOUTS: { text: string; left: string; top: string }[] = [
  { text: 'Your whole team, one chat', left: '4%', top: '3%' },
  { text: 'A lead, and why now', left: '27%', top: '51.5%' },
  { text: 'Saved only when you say', left: '55%', top: '74%' },
]

/** The hero's showcase: the real app, a Lace's team chat, captured with
 * example data (scripts/capture-app-shot.mjs). Callouts point out what to
 * notice, one after another, once it's on screen. */
export function AppShot() {
  const box = useRef<HTMLDivElement>(null)
  const { run, still } = usePlay(box)
  return (
    <DemoFrame status="The real app" live={false} detail="Thalace’s own Lace · example data">
      <div ref={box} className="relative">
        <picture>
          <source media="(max-width: 639px)" srcSet="/shots/lace-chat-phone.jpg" width={860} height={1050} />
          <img src="/shots/lace-chat.jpg" width={1632} height={1224} className="block h-auto w-full"
               alt="Thalace’s Lace in its team chat: asked who just raised and is hiring a first sales lead, it answers with two startups, Acme Pay (saved, two people to contact) and Globex Freight (waiting to be saved or dismissed), and suggests what to ask next." />
        </picture>
        <ul key={run} aria-hidden className="hidden sm:block">
          {CALLOUTS.map((c, i) => (
            <li key={c.text} className={`absolute flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-xs font-medium text-paper shadow-lift ${
              still ? '' : 'rise-in'}`}
                style={{ left: c.left, top: c.top, '--at': `${0.4 + i * 0.7}s` } as CSSProperties}>
              <span className="size-1.5 rounded-full bg-brand" />
              {c.text}
            </li>
          ))}
        </ul>
      </div>
    </DemoFrame>
  )
}
