import { useEffect, useRef, useState, type RefObject } from 'react'

import { ease, useScrollScenes, watchProgress } from '../lib/use-scroll-progress'
import { Lace, type LaceState } from './lace-mascot'
import { Section } from './section'

interface App {
  name: string
  /** Its icon in /apps; none draws its first letter instead. */
  icon?: string
  soon?: boolean
}

// The apps a Lace connects to today, by what it does with them (as in the app's settings).
const GROUPS: { label: string; blurb: string; apps: App[] }[] = [
  {
    label: 'Channels',
    blurb: 'Where it reaches people, reads their replies, and proposes posts and comment replies.',
    apps: [
      { name: 'Gmail', icon: 'gmail' }, { name: 'Outlook' }, { name: 'LinkedIn', icon: 'linkedin' }, { name: 'X' },
      { name: 'Instagram', icon: 'instagram' }, { name: 'Facebook', icon: 'facebook' },
      { name: 'TikTok', icon: 'tiktok-mark' }, { name: 'Telegram', icon: 'telegram' },
      { name: 'WhatsApp', icon: 'whatsapp', soon: true },
    ],
  },
  {
    label: 'CRM',
    blurb: 'Who is already a lead, and what your deals add up to.',
    apps: [{ name: 'HubSpot', icon: 'hubspot' }, { name: 'Zoho CRM', icon: 'zoho' }],
  },
  {
    label: 'Sheets & docs',
    blurb: 'Lead lists in and out, pages to read and write.',
    apps: [{ name: 'Google Sheets', icon: 'google-sheets' }, { name: 'Notion', icon: 'notion' }],
  },
  {
    label: 'Team & tasks',
    blurb: 'Your brief where your team works, follow-ups as tasks.',
    apps: [{ name: 'Slack', icon: 'slack' }, { name: 'Asana', icon: 'asana' }],
  },
  {
    label: 'Meetings',
    blurb: 'Free slots and booking links for whoever wants to talk.',
    apps: [{ name: 'Google Calendar', icon: 'google-calendar' }, { name: 'Calendly', icon: 'calendly' }],
  },
]

// What it proposes in those apps; each runs only on the founder's click.
const PROPOSALS: { ask: string; app: string; done: string }[] = [
  { ask: 'Post this on our LinkedIn', app: 'LinkedIn', done: 'Posted on LinkedIn' },
  { ask: 'Add Neema to HubSpot as a lead', app: 'HubSpot', done: 'Neema is in HubSpot' },
  { ask: 'Share the brief in #sales', app: 'Slack', done: 'Shared in #sales' },
  { ask: 'Put my booking link in the reply', app: 'Calendly', done: 'Booking link added' },
]
/** How long a proposal shows as running after Approve. */
const RUN_MS = 900

type Stage = 'proposed' | 'running' | 'done'

function AppIcon({ app }: { app: App }) {
  return app.icon ? (
    <img src={`/apps/${app.icon}.svg`} alt="" width={18} height={18} className="size-[18px]" loading="lazy" />
  ) : (
    <span aria-hidden className="grid size-[18px] place-items-center rounded bg-ink text-[10px] font-semibold text-paper">
      {app.name[0]}
    </span>
  )
}

function AppTile({ app, lit }: { app: App; lit: boolean }) {
  return (
    <li data-app className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm transition-colors duration-300 ${
      lit ? 'border-brand bg-highlight' : 'border-line bg-paper'} ${app.soon ? 'opacity-60' : ''}`}>
      <AppIcon app={app} />
      {app.name}
      {app.soon && <span className="text-xs text-muted">soon</span>}
    </li>
  )
}

function Spinner() {
  return <span aria-hidden className="size-3 animate-spin rounded-full border-2 border-paper/40 border-t-paper" />
}

/** One proposal, as in Lace's replies: Approve runs it (here, a demo that
 * runs nothing), and Undo puts it back. */
function Proposal({ ask, done, onFocusApp }: { ask: string; done: string; onFocusApp: (on: boolean) => void }) {
  const [stage, setStage] = useState<Stage>('proposed')
  const approve = () => {
    setStage('running')
    window.setTimeout(() => setStage('done'), RUN_MS)
  }
  return (
    <li data-proposal onPointerEnter={() => onFocusApp(true)} onPointerLeave={() => onFocusApp(false)}
        onFocus={() => onFocusApp(true)} onBlur={() => onFocusApp(false)}
        className={`flex min-h-12 items-center justify-between gap-3 rounded-lg border px-3 py-2 text-[14px] transition-colors duration-300 ${
          stage === 'done' ? 'border-kept/40 bg-kept/5' : 'border-line bg-panel'}`}>
      {stage === 'done' ? (
        <>
          <span className="pop-in flex items-center gap-2 font-medium text-kept">✓ {done}</span>
          <button type="button" onClick={() => setStage('proposed')}
                  className="shrink-0 cursor-pointer rounded-md px-2 py-1 text-xs text-muted hover:text-ink">Undo</button>
        </>
      ) : (
        <>
          <span>“{ask}”</span>
          <button type="button" onClick={approve} disabled={stage === 'running'} aria-label={`Approve: ${ask}`}
                  className="btn-primary shrink-0 px-2.5 py-1 text-xs disabled:bg-ink">
            {stage === 'running' ? <><Spinner /> Running</> : 'Approve'}
          </button>
        </>
      )}
      <span className="sr-only" aria-live="polite">{stage === 'done' ? done : ''}</span>
    </li>
  )
}

const ALL_APPS = GROUPS.flatMap((group) => group.apps)
// The scene's beats, as shares of its scroll: the apps' copies fly into Lace
// (each a little after the one before), then the proposals come out of it.
const FLY_SPREAD = 0.28
const FLY_EACH = 0.3
const OUT_FROM = 0.6
const OUT_EACH = 0.09
const OUT_TAKES = 0.12

const clamp = (t: number) => Math.min(1, Math.max(0, t))

/** On wide screens the section pins while the page scrolls through it: a
 * copy of each app's icon flies from its row into Lace, which thinks, then
 * its proposals come out one by one. Scrolling back reverses it. Positions
 * are set outside React's render; Lace's mood is the one piece of state. */
function useAppsIntoLace(stage: RefObject<HTMLDivElement | null>, lace: RefObject<HTMLSpanElement | null>,
                         track: RefObject<HTMLDivElement | null>, on: boolean): LaceState {
  const [mood, setMood] = useState<LaceState>('idle')
  useEffect(() => {
    const box = stage.current
    const el = track.current
    if (!box || !el) return
    const tiles = [...box.querySelectorAll<HTMLElement>('[data-app]')]
    const copies = [...box.querySelectorAll<HTMLElement>('[data-copy]')]
    const asks = [...box.querySelectorAll<HTMLElement>('[data-proposal]')]
    if (!on) {
      for (const node of [...copies, ...asks]) node.removeAttribute('style')
      return
    }
    return watchProgress(el, (p) => {
      const origin = box.getBoundingClientRect()
      const target = lace.current?.getBoundingClientRect()
      if (!target) return
      const tx = target.left + target.width / 2 - origin.left
      const ty = target.top + target.height / 2 - origin.top
      copies.forEach((copy, i) => {
        const from = tiles[i]?.getBoundingClientRect()
        if (!from) return
        const t = ease(clamp((p - (i / copies.length) * FLY_SPREAD) / FLY_EACH))
        const fx = from.left + 20 - origin.left
        const fy = from.top + from.height / 2 - origin.top
        // An arc: up and over, into Lace.
        const x = fx + (tx - fx) * t
        const y = fy + (ty - fy) * t - Math.sin(Math.PI * t) * 60
        copy.style.transform = `translate(${x - 15}px, ${y - 15}px) scale(${1 - 0.45 * t})`
        // Solid in flight, gone as it reaches Lace.
        copy.style.opacity = t > 0 && t < 1 ? String(Math.min(1, (1 - t) / 0.15)) : '0'
      })
      asks.forEach((ask, j) => {
        const t = ease(clamp((p - OUT_FROM - j * OUT_EACH) / OUT_TAKES))
        ask.style.opacity = String(t)
        ask.style.transform = t < 1 ? `translateY(${(1 - t) * -28}px) scale(${0.94 + 0.06 * t})` : ''
      })
      setMood(p < FLY_EACH * 0.6 ? 'idle' : p < OUT_FROM ? 'thinking' : 'alert')
    })
  }, [stage, lace, track, on])
  return on ? mood : 'idle'
}

export function YourTools() {
  // The app a proposal would act in, lit while it's pointed at or focused.
  const [focusApp, setFocusApp] = useState<string | null>(null)
  const scrub = useScrollScenes()
  const track = useRef<HTMLDivElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const lace = useRef<HTMLSpanElement>(null)
  const mood = useAppsIntoLace(stage, lace, track, scrub)
  return (
    <Section
      id="tools"
      title="It proposes. You approve. It runs."
      intro={<>Connect the apps your team already uses. Your Lace reads what it needs from them, and anything it would do there waits for your click.</>}
    >
      <div ref={track} className={scrub ? 'h-[240vh]' : ''}>
      <div ref={stage} className={`relative grid gap-10 lg:grid-cols-[1.4fr_1fr] lg:gap-16 ${
        scrub ? 'sticky top-14 h-[calc(100dvh-3.5rem)] content-center' : ''}`}>
        <div className="flex flex-col divide-y divide-line border-y border-line">
          {GROUPS.map((group) => (
            <div key={group.label} className="grid gap-3 py-5 sm:grid-cols-[11rem_1fr] sm:gap-6">
              <div>
                <h3 className="font-sans text-[15px] font-semibold">{group.label}</h3>
                <p className="mt-1 text-sm leading-snug text-muted">{group.blurb}</p>
              </div>
              <ul className="flex flex-wrap content-start gap-2" aria-label={group.label}>
                {group.apps.map((app) => <AppTile key={app.name} app={app} lit={app.name === focusApp} />)}
              </ul>
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-3 self-center rounded-xl bg-paper p-6 shadow-lift">
          <p className="flex items-center gap-2.5">
            <span ref={lace} className={`transition-transform duration-300 ${mood === 'thinking' ? 'scale-125' : ''}`}>
              <Lace state={mood} size={32} decorative />
            </span>
            <span className="tag text-sm">Ask, and approve</span>
          </p>
          <ul className="flex flex-col gap-2.5">
            {PROPOSALS.map((p) => (
              <Proposal key={p.ask} ask={p.ask} done={p.done}
                        onFocusApp={(on) => setFocusApp((current) => (on ? p.app : current === p.app ? null : current))} />
            ))}
          </ul>
          <p className="text-sm leading-relaxed text-muted">Nothing runs in your apps without that click. Try them: here, nothing is sent.</p>
        </div>
        {scrub && (
          // Copies of the apps' icons that fly into Lace; the rows keep theirs.
          <div aria-hidden className="pointer-events-none absolute inset-0 z-10">
            {ALL_APPS.map((app) => (
              <span key={app.name} data-copy
                    className="absolute top-0 left-0 grid size-[30px] place-items-center rounded-lg bg-panel opacity-0 shadow-md ring-1 ring-line">
                <AppIcon app={app} />
              </span>
            ))}
          </div>
        )}
      </div>
      </div>
    </Section>
  )
}
