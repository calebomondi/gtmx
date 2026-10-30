import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'

import { BornScene, OrbitScene, RoundTripScene } from './how-it-works-scenes'
import { Lace, type LaceState } from './lace-mascot'
import { Section } from './section'

const STEPS: { title: string; short: string; body: string; mood: LaceState }[] = [
  {
    title: 'Name your Lace, give it your website',
    short: 'Name it',
    body: 'It reads your site and shows you what it learned: what you sell, to whom, and how you stand out. You confirm or correct it, and invite your cofounders.',
    mood: 'idle',
  },
  {
    title: 'It gets to work, and keeps at it',
    short: 'It gets to work',
    body: 'Leads and the people to reach, places to sell and partner, grants you qualify for, competitors to watch, on a schedule you set. Ask it for more any time.',
    mood: 'thinking',
  },
  {
    title: 'You decide, then send',
    short: 'You decide',
    body: 'Approve who to contact, edit or brainstorm each draft, and send it from your own accounts. Replies come back with an answer drafted.',
    mood: 'alert',
  },
]

// What Lace acts out for each step, in order.
const SCENES = [BornScene, OrbitScene, RoundTripScene]

/** Pinned while scrolling through it only on wide screens with motion allowed. */
const STORY_QUERY = '(min-width: 1024px) and (prefers-reduced-motion: no-preference)'
/** The fixed site header's height, plus a little air: the pinned block never goes under it. */
const HEADER_CLEARANCE_PX = 72
/** Of each step's share of the scroll, the part Lace rests on its step before moving on. */
const REST = 0.6
const RIDER_PX = 28
/** A badge's centre, down from the top of its step. */
const BADGE_CENTRE_PX = 14

function prefersStill(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

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
function useScrollProgress(track: RefObject<HTMLElement | null>): number {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
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
  }, [track])
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

/** The sticky offset that centres `el` in the space below the header, by
 * its own height: a short block isn't pinned under an empty band. */
function useCentredTop(el: RefObject<HTMLElement | null>): number {
  const [top, setTop] = useState(HEADER_CLEARANCE_PX)
  useLayoutEffect(() => {
    const node = el.current
    if (!node) return
    const measure = () => {
      const free = window.innerHeight - HEADER_CLEARANCE_PX - node.offsetHeight
      setTop(HEADER_CLEARANCE_PX + Math.max(0, free / 2))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    window.addEventListener('resize', measure)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [el])
  return top
}

/** Where each step's badge sits down the list, as its centre in px. */
function useStops(items: RefObject<(HTMLLIElement | null)[]>, list: RefObject<HTMLElement | null>): number[] {
  const [stops, setStops] = useState<number[]>([])
  useLayoutEffect(() => {
    const node = list.current
    if (!node) return
    const measure = () => setStops(items.current.map((li) => (li ? li.offsetTop + BADGE_CENTRE_PX : 0)))
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [items, list])
  return stops
}

/** Where Lace is on the line: resting on a step for most of its share of the
 * scroll, then gliding to the next one as that step takes over. */
function riderAt(progress: number, stops: number[]): number {
  if (stops.length === 0) return 0
  const i = Math.min(stops.length - 1, Math.floor(progress * stops.length))
  if (i === stops.length - 1) return stops[i]
  const move = Math.max(0, (progress * stops.length - i - REST) / (1 - REST))
  const eased = move * move * (3 - 2 * move)
  return stops[i] + (stops[i + 1] - stops[i]) * eased
}

/** The paper card a scene plays on. Until it plays, it shows the scene's last
 * frame, faintly; it remounts to play, so it starts from the beginning. */
function Stage({ step, playing, className = '', sceneClassName = '' }: {
  step: number
  playing: boolean
  className?: string
  sceneClassName?: string
}) {
  const [reduced] = useState(prefersStill)
  const Scene = SCENES[step]
  const still = reduced || !playing
  return (
    <div aria-hidden className={`overflow-hidden rounded-2xl border border-line bg-paper shadow-card ${className}`}>
      <div key={`${step}:${still}`}
           className={`h-full p-6 ${still && !reduced ? 'opacity-45' : 'word-in'} ${sceneClassName}`}>
        <Scene still={still} />
      </div>
    </div>
  )
}

function Badge({ index, done }: { index: number; done: boolean }) {
  return (
    <span aria-hidden className="absolute top-0.5 -left-10 grid size-6 place-items-center rounded-md bg-brand font-mono text-[11px] font-semibold text-ink">
      {done ? '✓' : index + 1}
    </span>
  )
}

/** On wide screens: the steps on a line Lace rides down as you scroll, beside
 * a pinned stage where it acts out the step you're on. A step's title jumps
 * there. */
function Story() {
  const track = useRef<HTMLDivElement>(null)
  const pinned = useRef<HTMLDivElement>(null)
  const list = useRef<HTMLOListElement>(null)
  const items = useRef<(HTMLLIElement | null)[]>([])
  const progress = useScrollProgress(track)
  const onScreen = useOnScreen(pinned)
  const top = useCentredTop(pinned)
  const stops = useStops(items, list)
  const active = Math.min(STEPS.length - 1, Math.floor(progress * STEPS.length))
  const rider = riderAt(progress, stops)

  const goTo = (step: number) => {
    const el = track.current
    if (!el) return
    const start = el.getBoundingClientRect().top + window.scrollY
    const span = el.offsetHeight - window.innerHeight
    // A little into the step's share, where Lace is resting on it.
    window.scrollTo({ top: start + (span * (step + REST / 2)) / STEPS.length, behavior: 'smooth' })
  }

  return (
    <div ref={track} className="relative h-[200vh]">
      <div ref={pinned} style={{ top }} className="sticky grid grid-cols-[1fr_1.15fr] items-center gap-14">
        <ol ref={list} className="relative flex flex-col gap-10 pl-10">
          <span aria-hidden className="absolute top-2 bottom-2 left-[11px] w-0.5 rounded-full bg-ink/10" />
          <span aria-hidden className="absolute top-2 left-[11px] w-0.5 rounded-full bg-brand"
                style={{ height: Math.max(0, rider - 8) }} />
          {STEPS.map((step, i) => (
            <li key={step.title} ref={(li) => { items.current[i] = li }} aria-current={i === active ? 'step' : undefined}
                className="relative flex flex-col gap-2">
              <Badge index={i} done={stops.length > 0 && rider > stops[i] + 1} />
              <h3 className="text-xl font-semibold tracking-tight">
                <button type="button" onClick={() => goTo(i)}
                        className={`cursor-pointer text-left transition-colors duration-300 hover:text-ink ${i === active ? 'text-ink' : 'text-muted'}`}>
                  {step.title}
                </button>
              </h3>
              <p className="leading-relaxed text-muted">{step.body}</p>
            </li>
          ))}
          {/* Lace, riding the line: it covers the badge of the step it rests on. */}
          <span aria-hidden className="absolute top-0 left-[-2px] z-10 drop-shadow-md will-change-transform"
                style={{ transform: `translateY(${rider - RIDER_PX / 2}px)` }}>
            <Lace state={STEPS[active].mood} size={RIDER_PX} decorative />
          </span>
        </ol>
        <div className="flex flex-col gap-3">
          {/* The pinned stage is large: its scene is drawn larger to fill it. */}
          <Stage step={active} playing={onScreen} className="aspect-[4/3]" sceneClassName="scale-[1.2]" />
          <p aria-hidden className="text-center font-mono text-xs text-muted">
            Step {active + 1} of {STEPS.length} · {STEPS[active].short}
          </p>
        </div>
      </div>
    </div>
  )
}

/** On phones, or with reduced motion: each step with its own stage, which
 * plays when it scrolls into view. */
function StackedStep({ index }: { index: number }) {
  const item = useRef<HTMLLIElement>(null)
  const onScreen = useOnScreen(item)
  const step = STEPS[index]
  return (
    <li ref={item} className="relative flex flex-col gap-3">
      <Badge index={index} done={false} />
      <h3 className="text-xl font-semibold tracking-tight">{step.title}</h3>
      <p className="leading-relaxed text-muted">{step.body}</p>
      <Stage step={index} playing={onScreen} className="mt-2" />
    </li>
  )
}

export function HowItWorks() {
  const story = useStoryMode()
  return (
    <Section tone="bench" title="Three steps, and you stay in charge of every message.">
      {story ? (
        <Story />
      ) : (
        <ol className="relative flex flex-col gap-14 pl-10">
          <span aria-hidden className="absolute top-2 bottom-2 left-[11px] w-0.5 rounded-full bg-brand/60" />
          {STEPS.map((step, i) => <StackedStep key={step.title} index={i} />)}
        </ol>
      )}
    </Section>
  )
}
