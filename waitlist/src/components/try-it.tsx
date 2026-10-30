import { useId, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'

import { Lace } from './lace-mascot'
import { LaceSquare } from './lace-square'
import { Section } from './section'

interface Find {
  tag: string
  title: string
  why: string
  reach?: string
}

interface Startup {
  tab: string
  makes: string
  sellsTo: string
  finds: Find[]
  draft: { to: string; text: string }
}

// Invented startups and finds, described rather than named: none is a real
// company, group or person. Each shows what a Lace looks for given who the
// startup sells to.
const STARTUPS: Startup[] = [
  {
    tab: 'B2B software',
    makes: 'Booking software for private clinics',
    sellsTo: 'Businesses',
    finds: [
      { tag: 'Lead · strong fit', title: 'Clinic group, 6 branches', why: 'Opened two branches this year and is hiring a front-desk lead.', reach: 'Operations director · email' },
      { tag: 'Lead', title: 'Dental chain, 12 practices', why: 'A job post says it is moving to a new booking system.', reach: 'Practice manager · LinkedIn' },
      { tag: 'Place to sell · tender', title: 'County health department', why: 'Open call for a patient booking system. Closes in 18 days.' },
      { tag: 'Funding · grant', title: 'Health-tech innovation grant', why: 'Open to seed-stage teams in your country.' },
    ],
    draft: {
      to: 'the operations director',
      text: 'Congrats on the two new branches. Booking across six sites is where front desks lose hours; we fix that. Worth 15 minutes?',
    },
  },
  {
    tab: 'Consumer app',
    makes: 'A budgeting app for students',
    sellsTo: 'People',
    finds: [
      { tag: 'Community', title: 'Student money forum, 30k members', why: 'Weekly threads asking how to make rent last the month.', reach: 'The moderators · DM' },
      { tag: 'Creator', title: 'Personal-finance creator on TikTok', why: 'Mostly student followers; posts about rent and first jobs.', reach: 'Email in bio' },
      { tag: 'Showcase · event', title: 'Campus startup fair', why: 'Stalls for student-facing products. Applications close in 9 days.' },
      { tag: 'Partner', title: 'A student bank account', why: 'Serves the same students, and runs a partner programme.' },
    ],
    draft: {
      to: 'the forum’s moderators',
      text: 'Your members keep asking how to stretch rent money. Could we run a free budgeting session for them, no sign-up needed?',
    },
  },
  {
    tab: 'Services firm',
    makes: 'Bookkeeping for restaurants',
    sellsTo: 'Businesses',
    finds: [
      { tag: 'Lead · strong fit', title: 'Restaurant group, 4 sites', why: 'Just opened its fourth site.', reach: 'Owner · email' },
      { tag: 'Lead', title: 'Food hall operator', why: 'Posted a role for a finance lead last week.', reach: 'General manager · LinkedIn' },
      { tag: 'Place to sell · RFP', title: 'City hospitality association', why: 'Looking for an accounting partner for members. Closes in 14 days.' },
      { tag: 'Partner', title: 'Restaurant till software', why: 'Sells to the same restaurants, with a referral programme.' },
    ],
    draft: {
      to: 'the owner',
      text: 'Four sites means four sets of books. We close them every month for restaurant groups your size. Can I show you how?',
    },
  },
]

/** Where the spotlight square sits for each startup: under its tab, turned a little. */
const SPOTLIGHT = [
  'left-[-30%] -rotate-3 lg:left-[2%]',
  'left-[-10%] rotate-2 lg:left-[22%]',
  'left-[10%] rotate-6 lg:left-[42%]',
]

function rise(i: number): CSSProperties {
  return { '--at': `${i * 0.08}s` } as CSSProperties
}

function FindCard({ find, index }: { find: Find; index: number }) {
  return (
    <li className="rise-in rounded-lg border border-line bg-panel p-4 shadow-lift" style={rise(index)}>
      <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">{find.tag}</p>
      <p className="mt-1 font-semibold tracking-tight">{find.title}</p>
      <p className="mt-1 text-sm leading-snug text-muted">{find.why}</p>
      {find.reach && <p className="mt-2 text-[13px]"><span className="font-medium">Reach:</span> {find.reach}</p>}
    </li>
  )
}

/** Three example startups: pick one and see what its Lace would bring back,
 * so a founder sees it adapt to who they sell to. Tabs follow the ARIA tabs
 * pattern: arrow keys move between them. */
export function TryIt() {
  const id = useId()
  const [picked, setPicked] = useState(0)
  const tabs = useRef<(HTMLButtonElement | null)[]>([])
  const startup = STARTUPS[picked]

  const onKey = (event: KeyboardEvent) => {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    event.preventDefault()
    const next = (picked + step + STARTUPS.length) % STARTUPS.length
    setPicked(next)
    tabs.current[next]?.focus()
  }

  return (
    <Section
      id="try-it"
      decor={
        <LaceSquare className={`top-[34%] w-[110vw] transition-[left,rotate] duration-700 ease-out lg:top-[26%] lg:w-[min(52vw,46rem)] ${SPOTLIGHT[picked]}`} />
      }
      title="Try it on yours."
      intro={<>Pick a startup like yours and see what its Lace brings back. <strong>Who you sell to changes what it looks for</strong>: businesses with a reason to buy, or the places your customers already gather.</>}
    >
      <div className="flex flex-col gap-6">
        <div role="tablist" aria-label="Example startups" onKeyDown={onKey}
             className="grid grid-cols-3 gap-1 rounded-xl border border-line bg-panel p-1 sm:flex sm:w-fit">
          {STARTUPS.map((s, i) => (
            <button key={s.tab} ref={(el) => { tabs.current[i] = el }} type="button" role="tab" id={`${id}-tab-${i}`}
                    aria-selected={i === picked} aria-controls={`${id}-panel`} tabIndex={i === picked ? 0 : -1}
                    onClick={() => setPicked(i)}
                    className={`cursor-pointer rounded-lg px-2 py-2 text-[13px] font-medium whitespace-nowrap transition-colors sm:px-4 sm:text-sm ${
                      i === picked ? 'bg-ink text-paper' : 'text-muted hover:text-ink'}`}>
              {s.tab}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${picked}`}
             className="rounded-2xl border border-line bg-panel/60 p-4 sm:p-6">
          {/* Remounts per startup, so its finds rise in again. */}
          <div key={picked} className="flex flex-col gap-5">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <Lace state="alert" size={32} decorative />
              <p className="text-sm"><span className="text-muted">Makes:</span> <span className="font-medium">{startup.makes}</span></p>
              <p className="text-sm"><span className="text-muted">Sells to:</span> <span className="font-medium">{startup.sellsTo}</span></p>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted sm:ml-auto">Example · invented startups</span>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {startup.finds.map((find, i) => <FindCard key={find.title} find={find} index={i} />)}
            </ul>
            <div className="rise-in rounded-lg border border-dashed border-brand bg-panel p-4" style={rise(startup.finds.length)}>
              <p className="font-mono text-[10px] uppercase tracking-wider text-brand-ink">Draft · to {startup.draft.to}</p>
              <p className="mt-1.5 leading-snug">“{startup.draft.text}”</p>
              <p className="mt-2 text-[13px] text-muted">Waits for your click, like everything else.</p>
            </div>
          </div>
        </div>
      </div>
    </Section>
  )
}
