import { useEffect, useRef, useState, type RefObject } from 'react'

import { CreatedScene, StareScene, ThinkingScene } from './how-it-works-scenes'
import { Section } from './section'

const STEPS = [
  {
    title: 'Name your Lace, give it your website',
    body: 'It reads your site and shows you what it learned: what you sell, to whom, and how you stand out. You confirm or correct it, and invite your cofounders.',
  },
  {
    title: 'It gets to work, and keeps at it',
    body: 'Customers and the people to reach, places to sell and partner, competitors to watch, on a schedule you set. Ask it for more any time.',
  },
  {
    title: 'You decide, then send',
    body: 'Approve who to contact, edit or brainstorm each draft, and send it from your own accounts. Replies come back with an answer drafted.',
  },
]

// What Lace acts out for each step, in order.
const SCENES = [CreatedScene, ThinkingScene, StareScene]

/** Pinned while scrolling through it only on wide screens with motion allowed. */
const STORY_QUERY = '(min-width: 1024px) and (prefers-reduced-motion: no-preference)'

function useStoryMode(): boolean {
  const [story, setStory] = useState(() => typeof window !== 'undefined' && window.matchMedia(STORY_QUERY).matches)
  useEffect(() => {
    const query = window.matchMedia(STORY_QUERY)
    const update = () => setStory(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return story
}

/** How far the page has scrolled through `track`, 0 to 1, read once a frame. */
function useScrollProgress(track: RefObject<HTMLElement | null>, enabled: boolean): number {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    if (!enabled) return
    let frame = 0
    const read = () => {
      frame = 0
      const el = track.current
      if (!el) return
      const box = el.getBoundingClientRect()
      const span = box.height - window.innerHeight
      setProgress(span > 0 ? Math.min(1, Math.max(0, -box.top / span)) : 0)
    }
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(read)
    }
    read()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      cancelAnimationFrame(frame)
    }
  }, [track, enabled])
  return progress
}

/** Whether `el` is on screen (for the stacked layout's scenes). */
function useOnScreen(el: RefObject<HTMLElement | null>): boolean {
  const [on, setOn] = useState(false)
  useEffect(() => {
    if (!el.current) return
    const observer = new IntersectionObserver(([entry]) => setOn(entry.isIntersecting), { threshold: 0.4 })
    observer.observe(el.current)
    return () => observer.disconnect()
  }, [el])
  return on
}

/** The dark stage a scene plays on. The scene mounts only while `playing`,
 * and remounts per step, so it starts from the beginning each time it's seen. */
function Stage({ step, playing, className = '', sceneClassName = '' }: {
  step: number
  playing: boolean
  className?: string
  sceneClassName?: string
}) {
  const Scene = SCENES[step]
  return (
    <div aria-hidden className={`overflow-hidden rounded-2xl border border-night-line bg-night-line/40 ${className}`}>
      {playing && <div key={step} className={`word-in h-full p-6 ${sceneClassName}`}><Scene /></div>}
    </div>
  )
}

function StepText({ index, active }: { index: number; active: boolean }) {
  const step = STEPS[index]
  return (
    <>
      <span
        aria-hidden
        className={`absolute top-0.5 -left-10 grid size-6 place-items-center rounded-md bg-brand font-mono text-[11px] font-semibold text-ink ring-8 ring-night transition-transform duration-500 ${
          active ? 'scale-125' : ''}`}
      >
        {index + 1}
      </span>
      <h3 className="text-xl font-semibold tracking-tight">{step.title}</h3>
      <p className="leading-relaxed text-night-muted">{step.body}</p>
    </>
  )
}

/** On wide screens: the steps on a line that fills as you scroll, beside a
 * pinned stage where Lace acts out the step you're on. */
function Story() {
  const track = useRef<HTMLDivElement>(null)
  const pinned = useRef<HTMLDivElement>(null)
  const progress = useScrollProgress(track, true)
  const onScreen = useOnScreen(pinned)
  const active = Math.min(STEPS.length - 1, Math.floor(progress * STEPS.length))
  return (
    <div ref={track} className="relative h-[260vh]">
      <div ref={pinned} className="sticky top-14 grid h-[calc(100svh-3.5rem)] grid-cols-[1fr_1.15fr] items-center gap-14">
        <ol className="relative flex flex-col gap-10 pl-10">
          <span aria-hidden className="absolute top-2 bottom-2 left-[11px] w-px bg-night-line" />
          <span aria-hidden className="absolute top-2 left-[11px] w-px bg-brand transition-[height] duration-150"
                style={{ height: `calc(${progress * 100}% - 1rem)` }} />
          {STEPS.map((step, i) => (
            <li key={step.title} className={`relative flex flex-col gap-2 transition-opacity duration-500 ${i === active ? 'opacity-100' : 'opacity-40'}`}>
              <StepText index={i} active={i <= active} />
            </li>
          ))}
        </ol>
        {/* The pinned stage is large: its scene is drawn larger to fill it. */}
        <Stage step={active} playing={onScreen} className="aspect-[4/3]" sceneClassName="scale-125" />
      </div>
    </div>
  )
}

/** On phones, or with reduced motion: each step with its own stage, which
 * plays when it scrolls into view. */
function StackedStep({ index }: { index: number }) {
  const item = useRef<HTMLLIElement>(null)
  const onScreen = useOnScreen(item)
  return (
    <li ref={item} className="relative flex flex-col gap-3">
      <StepText index={index} active />
      <Stage step={index} playing={onScreen} className="mt-2 grid min-h-80" />
    </li>
  )
}

export function HowItWorks() {
  const story = useStoryMode()
  return (
    <Section tone="night" label="How it works" title="Three steps, and you stay in charge of every message.">
      {story ? (
        <Story />
      ) : (
        <ol className="relative flex flex-col gap-14 pl-10">
          <span aria-hidden className="absolute top-2 bottom-2 left-[11px] w-px bg-brand/60" />
          {STEPS.map((step, i) => <StackedStep key={step.title} index={i} />)}
        </ol>
      )}
    </Section>
  )
}
