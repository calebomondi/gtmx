import { useState } from 'react'

import { stagger } from '../lib/stagger'
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

function AppTile({ app, lit }: { app: App; lit: boolean }) {
  return (
    <li className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-sm transition-colors duration-300 ${
      lit ? 'border-brand bg-highlight' : 'border-line bg-paper'} ${app.soon ? 'opacity-60' : ''}`}>
      {app.icon ? (
        <img src={`/apps/${app.icon}.svg`} alt="" width={18} height={18} className="size-[18px]" loading="lazy" />
      ) : (
        <span aria-hidden className="grid size-[18px] place-items-center rounded bg-ink text-[10px] font-semibold text-paper">
          {app.name[0]}
        </span>
      )}
      {app.name}
      {app.soon && <span className="font-mono text-[10px] uppercase tracking-wider text-muted">Soon</span>}
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
    <li onPointerEnter={() => onFocusApp(true)} onPointerLeave={() => onFocusApp(false)}
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

export function YourTools() {
  // The app a proposal would act in, lit while it's pointed at or focused.
  const [focusApp, setFocusApp] = useState<string | null>(null)
  return (
    <Section
      id="tools"
      tone="white"
      title="It proposes. You approve. It runs."
      intro={<>Connect the apps your team already uses. Your Lace reads what it needs from them, and <strong>anything it would do there waits for your click</strong>.</>}
    >
      <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr] lg:gap-16">
        <div className="flex flex-col divide-y divide-line border-y border-line">
          {GROUPS.map((group, g) => (
            <div key={group.label} data-reveal style={stagger(g)} className="grid gap-3 py-5 sm:grid-cols-[11rem_1fr] sm:gap-6">
              <div>
                <h3 className="font-mono text-xs uppercase tracking-wider text-brand-ink">{group.label}</h3>
                <p className="mt-1 text-sm leading-snug text-muted">{group.blurb}</p>
              </div>
              <ul className="flex flex-wrap content-start gap-2" aria-label={group.label}>
                {group.apps.map((app) => <AppTile key={app.name} app={app} lit={app.name === focusApp} />)}
              </ul>
            </div>
          ))}
        </div>
        <div data-reveal style={stagger(2)} className="flex flex-col gap-3 self-center rounded-xl bg-paper p-6 shadow-lift">
          <p className="font-mono text-xs uppercase tracking-wider text-brand-ink">Ask, and approve</p>
          <ul className="flex flex-col gap-2.5">
            {PROPOSALS.map((p) => (
              <Proposal key={p.ask} ask={p.ask} done={p.done}
                        onFocusApp={(on) => setFocusApp((current) => (on ? p.app : current === p.app ? null : current))} />
            ))}
          </ul>
          <p className="text-sm leading-relaxed text-muted">Nothing runs in your apps without that click. Try them: here, nothing is sent.</p>
        </div>
      </div>
    </Section>
  )
}
