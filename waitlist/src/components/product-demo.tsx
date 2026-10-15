import { useEffect, useRef, useState } from 'react'

import { DemoFrame } from './demo-frame'
import type { DemoVideo } from './demo-video'

function prefersStill(): boolean {
  if (typeof window === 'undefined') return true
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData === true
  return reduced || saveData
}

/** The real product, recorded and sped up. The poster paints first (it is
 * the hero's largest image); the video only loads once the page has loaded
 * and plays only while on screen. With reduced motion or data saver it waits
 * for a click. Captions are HTML, timed to the clip, so they stay sharp and
 * readable by assistive tech. */
export function ProductDemo({ video }: { video: DemoVideo }) {
  const frame = useRef<HTMLDivElement>(null)
  const player = useRef<HTMLVideoElement>(null)
  const [autoplay] = useState(() => !prefersStill())
  const [playing, setPlaying] = useState(false)
  const [caption, setCaption] = useState(video.captions[0]?.text ?? '')

  // Play while in view (after the page has loaded); pause when scrolled away.
  useEffect(() => {
    const el = player.current
    if (!autoplay || !el || !frame.current) return
    let visible = false
    let loaded = document.readyState === 'complete'
    const sync = () => {
      if (visible && loaded) el.play().catch(() => setPlaying(false))
      else el.pause()
    }
    const onLoad = () => {
      loaded = true
      sync()
    }
    window.addEventListener('load', onLoad)
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting
      sync()
    }, { threshold: 0.25 })
    observer.observe(frame.current)
    return () => {
      window.removeEventListener('load', onLoad)
      observer.disconnect()
    }
  }, [autoplay])

  const onTime = () => {
    const t = player.current?.currentTime ?? 0
    const current = [...video.captions].reverse().find((c) => c.at <= t)
    if (current && current.text !== caption) setCaption(current.text)
  }

  const toggle = () => {
    const el = player.current
    if (!el) return
    if (el.paused) el.play().catch(() => setPlaying(false))
    else el.pause()
  }

  return (
    <DemoFrame status="Real product" live={playing} detail={`Sped up · ${video.subject}`}>
      <div ref={frame} className="relative aspect-[4/3] bg-paper">
        <video
          ref={player}
          className="absolute inset-0 h-full w-full object-cover"
          poster={video.poster}
          muted
          loop
          playsInline
          preload="none"
          aria-label={`Recording of Thalace researching ${video.subject}, sped up`}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={onTime}
        >
          <source src={video.webm} type="video/webm" />
          <source src={video.mp4} type="video/mp4" />
        </video>

        {caption && (
          <p
            aria-hidden
            className="absolute bottom-3 left-3 max-w-[calc(100%-4.5rem)] rounded-md bg-ink/85 px-3 py-1.5 text-[13px] font-medium text-paper backdrop-blur-sm"
          >
            {caption}
          </p>
        )}
        <button
          type="button"
          onClick={toggle}
          aria-label={playing ? 'Pause the product recording' : 'Play the product recording'}
          className="absolute right-3 bottom-3 grid size-10 cursor-pointer place-items-center rounded-full bg-brand text-ink shadow-lift transition hover:bg-panel"
        >
          {playing ? (
            <svg viewBox="0 0 16 16" className="size-4" aria-hidden><rect x="3.5" y="3" width="3" height="10" rx="0.5" fill="currentColor" /><rect x="9.5" y="3" width="3" height="10" rx="0.5" fill="currentColor" /></svg>
          ) : (
            <svg viewBox="0 0 16 16" className="size-4" aria-hidden><path d="M5 3.2v9.6a.5.5 0 0 0 .76.43l7.6-4.8a.5.5 0 0 0 0-.86l-7.6-4.8A.5.5 0 0 0 5 3.2Z" fill="currentColor" /></svg>
          )}
        </button>
      </div>
      {/* The whole story for screen readers, rather than captions changing under them. */}
      <ol className="sr-only">
        {video.captions.map((c) => <li key={c.at}>{c.text}</li>)}
      </ol>
    </DemoFrame>
  )
}

/** The frame without a recording yet: a blank 4:3 panel holding the space
 * the video will fill, so the hero's layout doesn't move when it arrives. */
export function DemoPlaceholder() {
  return (
    <DemoFrame status="Real product" live={false} detail="Recording coming soon">
      <div className="aspect-[4/3] bg-panel" />
    </DemoFrame>
  )
}
