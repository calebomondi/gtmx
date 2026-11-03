import { useEffect, useRef } from 'react'

import { useScrollScenes, watchPassage } from '../lib/use-scroll-progress'

/** How faint a word is before the scroll reaches it. */
const UNLIT = 0.18

/** A headline that lights up word by word as it passes up the screen, and
 * dims again as you scroll back. Read whole by screen readers; with reduced
 * motion it's plain text. */
export function ScrollWords({ text }: { text: string }) {
  const box = useRef<HTMLSpanElement>(null)
  const on = useScrollScenes(0)
  const words = text.split(' ')
  useEffect(() => {
    const el = box.current
    if (!el) return
    const spans = [...el.querySelectorAll<HTMLElement>('[data-word]')]
    if (!on) {
      spans.forEach((span) => span.removeAttribute('style'))
      return
    }
    return watchPassage(el, (p) => {
      // Each word lights over its own slice of the scroll, overlapping the next.
      spans.forEach((span, i) => {
        const lit = Math.min(1, Math.max(0, p * (spans.length + 1) - i))
        span.style.opacity = String(UNLIT + (1 - UNLIT) * lit)
      })
    })
  }, [on])
  return (
    <>
      <span className="sr-only">{text}</span>
      <span ref={box} aria-hidden>
        {words.map((word, i) => (
          <span key={i} data-word className="transition-opacity duration-150">
            {word}{i < words.length - 1 ? ' ' : ''}
          </span>
        ))}
      </span>
    </>
  )
}
