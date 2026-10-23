import { useState, type FormEvent } from 'react'

import { EXPECTATIONS_MAX_CHARS, type PilotSpots, type SellsTo, type Stage, type WaitlistDetails } from '../../lib/api'
import { Choice, Pill } from './choice'
import { HOME_MARKETS, SELLS_TO, STAGES } from './options'

const inputClass =
  'h-11 w-full rounded-md border border-line bg-panel px-3 text-base outline-none transition focus:border-ink'

/** Step two, all optional: a pilot spot, and enough about them to set it up. */
export function DetailsStep({
  email,
  pilot,
  busy,
  error,
  onSave,
  onSkip,
}: {
  email: string
  pilot: PilotSpots | null
  busy: boolean
  error: string | null
  onSave: (details: WaitlistDetails) => void
  onSkip: () => void
}) {
  const pilotOpen = pilot === null || pilot.left > 0
  const [wantsPilot, setWantsPilot] = useState(pilotOpen)
  const [name, setName] = useState('')
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [stage, setStage] = useState<Stage | undefined>()
  const [sellsTo, setSellsTo] = useState<SellsTo | undefined>()
  const [countries, setCountries] = useState<string[]>(HOME_MARKETS)
  const [other, setOther] = useState('')
  const [expectations, setExpectations] = useState('')

  const toggleCountry = (country: string) =>
    setCountries((list) => (list.includes(country) ? list.filter((c) => c !== country) : [...list, country]))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const extra = other.split(',').map((c) => c.trim()).filter(Boolean)
    onSave({
      wants_pilot: wantsPilot,
      name: name || undefined,
      company: company || undefined,
      role: role || undefined,
      stage,
      sells_to: sellsTo,
      countries: [...countries, ...extra],
      expectations: expectations || undefined,
    })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-wider text-kept">On the list</p>
        <h2 className="mt-1 text-xl font-semibold text-balance">You're in, {email}.</h2>
        <p className="mt-1 text-sm text-muted">Two minutes more helps us set up your pilot. Everything here is optional.</p>
      </div>

      <label
        className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition ${
          wantsPilot ? 'border-brand bg-highlight/60' : 'border-line bg-panel'
        } ${pilotOpen ? '' : 'opacity-60'}`}
      >
        <input
          type="checkbox"
          checked={wantsPilot}
          disabled={!pilotOpen}
          onChange={(e) => setWantsPilot(e.target.checked)}
          className="mt-1 size-4 shrink-0 cursor-pointer accent-ink"
        />
        <span className="flex flex-col gap-1">
          <span className="font-semibold">Join the pilot</span>
          <span className="text-sm text-muted">
            {pilotOpen
              ? `Free access, a direct line to the team, and a say in what we build. We contact pilots within two weeks.${
                  pilot ? ` ${pilot.left} of ${pilot.total} spots left.` : ''
                }`
              : 'All pilot spots are taken. You stay on the waitlist and hear first when we open more.'}
          </span>
        </span>
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          Your name
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={120} />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          Role
          <input className={inputClass} value={role} onChange={(e) => setRole(e.target.value)} placeholder="Founder, Head of Sales…" maxLength={120} />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium sm:col-span-2">
          Company or website
          <input className={inputClass} value={company} onChange={(e) => setCompany(e.target.value)} autoComplete="organization" placeholder="Acme" maxLength={200} />
        </label>
      </div>

      <Choice legend="What stage are you at?" options={STAGES} value={stage} onChange={setStage} />
      <Choice legend="Who do you sell to?" options={SELLS_TO} value={sellsTo} onChange={setSellsTo} />

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium">Where do you sell?</legend>
        <div className="flex flex-wrap gap-2">
          {HOME_MARKETS.map((country) => (
            <Pill key={country} pressed={countries.includes(country)} onClick={() => toggleCountry(country)}>
              {country}
            </Pill>
          ))}
        </div>
        <input className={inputClass} value={other} onChange={(e) => setOther(e.target.value)} placeholder="Other countries, comma separated" aria-label="Other countries" maxLength={200} />
      </fieldset>

      <label className="flex flex-col gap-1.5 text-sm font-medium">
        What should Thalace do for you?
        <textarea
          value={expectations}
          onChange={(e) => setExpectations(e.target.value.slice(0, EXPECTATIONS_MAX_CHARS))}
          rows={3}
          placeholder="e.g. Find clinics that need our scheduling tool, and a conference to show it at."
          className="w-full resize-none rounded-md border border-line bg-panel px-3 py-2.5 text-base outline-none transition focus:border-ink"
        />
        <span className="self-end font-mono text-xs text-muted tabular-nums">
          {expectations.length}/{EXPECTATIONS_MAX_CHARS}
        </span>
      </label>

      {error && (
        <p role="alert" className="text-sm text-dropped">
          {error}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={busy}
          className="btn-primary h-11 px-5 text-sm"
        >
          {busy ? 'Saving…' : wantsPilot ? 'Save and join the pilot' : 'Save'}
        </button>
        <button type="button" onClick={onSkip} className="cursor-pointer text-sm text-muted underline-offset-4 hover:underline">
          Skip for now
        </button>
      </div>
    </form>
  )
}
