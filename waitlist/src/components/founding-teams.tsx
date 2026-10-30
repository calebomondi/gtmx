import { useEffect, useRef, useState, type ReactNode, type SVGProps } from 'react'

import { usePlay } from '../lib/motion'
import { stagger } from '../lib/stagger'
import { Lace } from './lace-mascot'
import { Section } from './section'

function Icon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" width={20} height={20} fill="none" stroke="currentColor" strokeWidth={2}
         strokeLinecap="round" strokeLinejoin="round" {...props} />
  )
}

/** Two people, one in front of the other. */
function Cofounders() {
  return (
    <Icon>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
      <path d="M14.5 4.7a3.5 3.5 0 0 1 0 6.6" />
      <path d="M18 14.2a6.5 6.5 0 0 1 3.5 5.8" />
    </Icon>
  )
}

function Padlock() {
  return (
    <Icon>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </Icon>
  )
}

/** Two message bubbles, one over the other: several talks going at once. */
function Conversations() {
  return (
    <Icon>
      <path d="M14 10a1.5 1.5 0 0 1-1.5 1.5H7L3 15V4.5A1.5 1.5 0 0 1 4.5 3h8A1.5 1.5 0 0 1 14 4.5z" />
      <path d="M17.5 8h2A1.5 1.5 0 0 1 21 9.5V21l-4-3.5h-5.5a1.5 1.5 0 0 1-1.5-1.5v-1.5" />
    </Icon>
  )
}

/** The orange square each point's icon sits in, as wide as Lace beside it. */
function Badge({ children }: { children: ReactNode }) {
  return <span className="grid size-9 place-items-center rounded-lg bg-brand text-ink">{children}</span>
}

// Thalace's own team chat, as in the hero's example. The people are "you" and "your cofounder", and the
// startups invented: none is a real company or person.
const POINTS: { title: string; body: string; icon: ReactNode }[] = [
  {
    icon: <Lace state="idle" size={36} decorative />,
    title: 'One Lace per startup',
    body: 'One memory of what you sell, who buys, every competitor and every conversation. Nobody re-explains the startup, to Lace or to each other.',
  },
  {
    icon: <Badge><Cofounders /></Badge>,
    title: 'Your cofounders, on the same Lace',
    body: 'Invite them by email. The team chat shows who asked what, and Lace answers each of you by name.',
  },
  {
    icon: <Badge><Padlock /></Badge>,
    title: 'A private chat for each of you',
    body: 'Think out loud in “Just you”. What it finds there stays yours until you push it, with a note, and a cofounder approves it for the team.',
  },
  {
    icon: <Badge><Conversations /></Badge>,
    title: 'All of you, at once',
    body: 'Ask while searches run in the background. Messages wait their turn, nothing gets lost, and results arrive marked when they’re in.',
  },
]

function Avatar({ initial, tone }: { initial: string; tone: 'ink' | 'brand' }) {
  return (
    <span aria-hidden className={`grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold ${
      tone === 'ink' ? 'bg-ink text-paper' : 'bg-highlight text-brand-ink'}`}>
      {initial}
    </span>
  )
}

/** A founder's message, signed: in a team, Lace and everyone see who asked. */
function Said({ who, initial, tone, children, waiting = false }: {
  who: string
  initial: string
  tone: 'ink' | 'brand'
  children: ReactNode
  waiting?: boolean
}) {
  return (
    <div className="flex items-start justify-end gap-2">
      <div className="flex flex-col items-end gap-0.5">
        <p className="font-mono text-[10px] uppercase tracking-wider text-muted">{who}</p>
        <p className={`max-w-[15rem] rounded-lg bg-highlight px-2.5 py-1.5 text-[13px] leading-snug ${waiting ? 'opacity-60' : ''}`}>
          {children}
        </p>
        {waiting && <p className="text-[11px] text-muted">Waiting its turn</p>}
      </div>
      <Avatar initial={initial} tone={tone} />
    </div>
  )
}

/** The chat's beats, in ms from the start: who says what, and when. */
const BEATS = {
  asked: 300,
  typing: 900,
  answered: 2000,
  cofounder: 2600,
  searching: 3100,
  answeredCofounder: 4300,
  pushed: 5300,
  approved: 6600,
} as const
type Beat = keyof typeof BEATS | 'start'
const ORDER: Beat[] = ['start', 'asked', 'typing', 'answered', 'cofounder', 'searching', 'answeredCofounder', 'pushed', 'approved']

/** Which point beside the chat each beat shows (POINTS' index). */
function pointAt(beat: Beat): number {
  if (beat === 'start') return 0
  if (ORDER.indexOf(beat) < ORDER.indexOf('cofounder')) return 1
  if (ORDER.indexOf(beat) < ORDER.indexOf('pushed')) return 3
  return 2
}

/** The chat's beat: it walks through BEATS once per run, and sits on the last when still. */
function useBeat(run: number, still: boolean): Beat {
  // Tagged with its run, so a replay reads as the start until its first beat lands.
  const [reached, setReached] = useState<{ run: number; beat: Beat }>({ run, beat: 'start' })
  useEffect(() => {
    if (still) return
    const timers = (Object.keys(BEATS) as (keyof typeof BEATS)[])
      .map((beat) => window.setTimeout(() => setReached({ run, beat }), BEATS[beat]))
    return () => timers.forEach((t) => window.clearTimeout(t))
  }, [run, still])
  if (still) return 'approved'
  return reached.run === run ? reached.beat : 'start'
}

/** Shown from `from` on, rising in as it arrives; until then it keeps its
 * place, so the chat doesn't jump as it fills. */
function Arrive({ beat, from, still, className = '', children }: {
  beat: Beat
  from: Beat
  still: boolean
  className?: string
  children: ReactNode
}) {
  const shown = ORDER.indexOf(beat) >= ORDER.indexOf(from)
  return <div className={`${className} ${shown ? (still ? '' : 'rise-in') : 'invisible'}`}>{children}</div>
}

function Typing() {
  return (
    <span className="flex items-center gap-1 py-1.5" aria-hidden>
      {[0, 1, 2].map((i) => <span key={i} className="typing-dot size-1.5 rounded-full bg-ink/40" style={{ animationDelay: `${i * 0.15}s` }} />)}
    </span>
  )
}

/** A founding team on one Lace, played out: you ask and Lace answers, your
 * cofounder's message waits its turn while a search runs, then a find your
 * cofounder pushed from their private chat is approved. */
function TeamChat({ beat, still }: { beat: Beat; still: boolean }) {
  const at = (from: Beat) => ORDER.indexOf(beat) >= ORDER.indexOf(from)
  const working = !at('answered') || (at('searching') && !at('answeredCofounder'))
  const lace = !at('typing') || at('approved') ? 'idle' : working ? 'thinking' : 'alert'
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-paper shadow-lift" role="img"
         aria-label="Two cofounders in their Lace's team chat, with a search running and a find to review">
      <div className="flex items-center gap-3 border-b border-line bg-panel px-4 py-3">
        <Lace state={lace} size={28} decorative />
        <div><p className="text-sm font-semibold leading-tight">Lace</p><p className="text-[11px] text-muted">thalace.com</p></div>
        <div className="ml-auto flex rounded-full border border-line bg-paper p-0.5 text-[11px]">
          <span className="rounded-full bg-panel px-2.5 py-0.5 font-medium shadow-lift">Team chat</span>
          <span className="px-2.5 py-0.5 text-muted">Just you</span>
        </div>
      </div>
      <div className="flex flex-col gap-3 p-4 sm:p-5">
        <Arrive beat={beat} from="asked" still={still}>
          <Said who="You" initial="Y" tone="brand">Who just raised and is hiring their first sales lead?</Said>
        </Arrive>
        <Arrive beat={beat} from="typing" still={still} className="flex items-start gap-2">
          <Lace state="alert" size={24} decorative />
          {at('answered') ? (
            <p className={`max-w-[17rem] text-[13px] leading-snug ${still ? '' : 'rise-in'}`}>
              Three startups. Acme Pay raised its seed round in June and is hiring a head of sales.
            </p>
          ) : <Typing />}
        </Arrive>
        <Arrive beat={beat} from="cofounder" still={still}>
          <Said who="Your cofounder" initial="C" tone="ink" waiting={!at('answeredCofounder')}>Draft one to Acme Pay’s founder</Said>
        </Arrive>
        <Arrive beat={beat} from="searching" still={still}
                className="flex w-fit items-center gap-2 rounded-full border border-brand/50 bg-highlight/50 px-3 py-1 text-[12px]">
          <span aria-hidden className="size-2 animate-pulse rounded-full bg-brand" />
          Searching for partners · 2m
          <span className="text-muted">Keep chatting</span>
        </Arrive>
        <Arrive beat={beat} from="answeredCofounder" still={still} className="flex items-start gap-2">
          <Lace state="idle" size={24} decorative />
          <p className="max-w-[17rem] text-[13px] leading-snug">Drafted for Neema, Acme Pay’s founder. It’s in Messaging when you’re ready.</p>
        </Arrive>
        <Arrive beat={beat} from="pushed" still={still} className="rounded-lg border border-line bg-panel p-3 shadow-lift">
          <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">To review · from your cofounder’s chat</p>
          <p className="mt-1 font-semibold tracking-tight">Launchpad accelerator</p>
          <p className="mt-0.5 text-[13px] leading-snug text-muted">Partner: runs programmes for the startups we sell to</p>
          <p className="mt-1.5 rounded-md bg-paper px-2 py-1 text-[12px]">“Met their programme lead at a demo day.”</p>
          <div className="mt-2.5 flex items-center justify-end gap-1.5 text-xs">
            {at('approved') ? (
              <span className={`rounded-md bg-kept px-2.5 py-1 font-semibold text-panel ${still ? '' : 'pop-in'}`}>✓ Approved by you</span>
            ) : (
              <>
                <span className="rounded-md border border-line px-2.5 py-1">Send back</span>
                <span className="rounded-md bg-ink px-2.5 py-1 font-semibold text-paper">Approve</span>
              </>
            )}
          </div>
        </Arrive>
      </div>
    </div>
  )
}

export function FoundingTeams() {
  const stage = useRef<HTMLDivElement>(null)
  const { run, still, replay } = usePlay(stage)
  const beat = useBeat(run, still)
  // While it plays, the point it's showing stands out; once done, all read alike.
  const lit = !still && beat !== 'approved' ? pointAt(beat) : null
  return (
    <Section
      id="teams"
      tone="table"
      title="One startup. One Lace. Everyone on it."
      intro={<>A startup is rarely one person. Your Lace is <strong>shared by the whole founding team</strong>, so what one of you learns, all of you can build on.</>}
    >
      <div className="grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-center lg:gap-16">
        <div ref={stage} className="flex flex-col gap-3">
          <TeamChat key={run} beat={beat} still={still} />
          {!still && beat === 'approved' && (
            <button type="button" onClick={replay} className="cursor-pointer self-start text-sm text-muted underline-offset-4 hover:text-ink hover:underline">
              Play it again
            </button>
          )}
        </div>
        <ul className="flex flex-col gap-7">
          {POINTS.map((point, i) => (
            <li key={point.title} data-reveal style={stagger(i)}>
              {/* Dimmed on an inner box: the reveal owns the item's own opacity. */}
              <div className={`flex gap-4 transition-opacity duration-500 ${lit === null || lit === i ? '' : 'opacity-40'}`}>
                <span className={`shrink-0 transition-transform duration-500 ${lit === i ? 'scale-110' : ''}`}>{point.icon}</span>
                <div>
                  <p className="text-lg font-semibold tracking-tight">{point.title}</p>
                  <p className="mt-1 leading-relaxed text-muted">{point.body}</p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  )
}
