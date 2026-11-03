import { useEffect, useState } from 'react'

import { prefersStill } from './motion'

/** Height of the sticky site header, which a pinned scene sits below. */
export const HEADER_PX = 56

/** Follow how far the page has scrolled through `track`, from 0 (its top
 * reaches the header) to 1 (its bottom reaches the bottom of the screen): the
 * progress of a scene pinned inside it. `onProgress` runs at most once a
 * frame; call this from an effect, and return what it returns to stop. */
export function watchProgress(track: HTMLElement, onProgress: (p: number) => void): () => void {
  let frame = 0
  const update = () => {
    frame = 0
    const box = track.getBoundingClientRect()
    const run = box.height - (window.innerHeight - HEADER_PX)
    onProgress(run > 0 ? Math.min(1, Math.max(0, (HEADER_PX - box.top) / run)) : 0)
  }
  const schedule = () => { frame ||= requestAnimationFrame(update) }
  update()
  window.addEventListener('scroll', schedule, { passive: true })
  window.addEventListener('resize', schedule)
  return () => {
    cancelAnimationFrame(frame)
    window.removeEventListener('scroll', schedule)
    window.removeEventListener('resize', schedule)
  }
}

/** Whether scroll-driven scenes run: on screens at least `minWidth` wide, and
 * never with reduced motion. Follows the window as it's resized. */
export function useScrollScenes(minWidth = 1024): boolean {
  const query = `(min-width: ${minWidth}px)`
  const [on, setOn] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches && !prefersStill())
  useEffect(() => {
    const wide = window.matchMedia(query)
    const onChange = () => setOn(wide.matches && !prefersStill())
    wide.addEventListener('change', onChange)
    return () => wide.removeEventListener('change', onChange)
  }, [query])
  return on
}

/** 0→1 eased in and out, so a scene starts and settles gently. */
export function ease(p: number): number {
  return p < 0.5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2
}
