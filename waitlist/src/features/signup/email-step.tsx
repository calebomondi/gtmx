import { useId, useRef, useState, type FormEvent } from 'react'

import type { PilotSpots } from '../../lib/api'

/** Step one: an email, and whether they want a pilot spot. Everything else is
 * optional, later. Joining is the agreement to be emailed, said under the button. */
export function EmailStep({
  pilot,
  busy,
  error,
  onJoin,
}: {
  pilot: PilotSpots | null
  busy: boolean
  error: string | null
  onJoin: (email: string, nickname: string, wantsPilot: boolean) => void
}) {
  // Unique per form: the signup appears twice on the page.
  const id = useId()
  const [email, setEmail] = useState('')
  const [nickname, setNickname] = useState('')
  const [missingEmail, setMissingEmail] = useState(false)
  const [pilotTicked, setPilotTicked] = useState(true)
  const emailField = useRef<HTMLInputElement>(null)
  // Spots unknown yet (still loading) counts as open.
  const pilotOpen = pilot === null || pilot.left > 0
  const wantsPilot = pilotOpen && pilotTicked

  // The button always looks ready: what is missing is said under its field
  // on submit, rather than left for a greyed-out button to hint at.
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    if (!email.trim() || !emailField.current?.checkValidity()) {
      setMissingEmail(true)
      emailField.current?.focus()
    } else {
      onJoin(email, nickname, wantsPilot)
    }
  }

  // noValidate: the browser's own bubble would show before these inline errors.
  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3">
      <label htmlFor={`${id}-email`} className="text-sm font-medium">
        Founder or startup email
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          ref={emailField}
          id={`${id}-email`}
          type="email"
          required
          autoComplete="email"
          inputMode="email"
          placeholder="you@yourstartup.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            setMissingEmail(false)
          }}
          aria-invalid={missingEmail}
          aria-describedby={missingEmail ? `${id}-email-error` : undefined}
          className="h-12 w-full min-w-0 rounded-md border border-ink/20 bg-panel px-3.5 text-base outline-none transition focus:border-ink focus:ring-4 focus:ring-brand/40 sm:flex-1"
        />
        <button
          type="submit"
          disabled={busy}
          className="btn-primary h-12 shrink-0 px-5 text-sm"
        >
          {busy ? 'Joining…' : wantsPilot ? 'Join the pilot' : 'Join the waitlist'}
        </button>
      </div>
      {missingEmail && (
        <p id={`${id}-email-error`} role="alert" className="-mt-1 text-sm text-dropped">
          Enter your email.
        </p>
      )}
      {/* Hidden from people, filled by bots. */}
      <input
        type="text"
        name="nickname"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        value={nickname}
        onChange={(e) => setNickname(e.target.value)}
        className="absolute -left-[9999px] h-px w-px opacity-0"
      />
      <label className={`flex items-start gap-2.5 text-sm leading-snug ${pilotOpen ? 'cursor-pointer' : 'opacity-60'}`}>
        <input
          type="checkbox"
          checked={wantsPilot}
          disabled={!pilotOpen}
          onChange={(e) => setPilotTicked(e.target.checked)}
          className="mt-0.5 size-4 shrink-0 cursor-pointer accent-ink disabled:cursor-default"
        />
        <span>
          {pilotOpen ? (
            <>
              <span className="font-semibold">Get a pilot spot:</span> your own Lace, free.
              {pilot && ` ${pilot.left} of ${pilot.total} left.`}
            </>
          ) : (
            "All pilot spots are taken. You'll hear first when we open more."
          )}
        </span>
      </label>
      <p className="text-[13px] leading-snug text-muted">
        By joining, you agree we can email you about your spot. Unsubscribe anytime.
      </p>
      {error && (
        <p role="alert" className="text-sm text-dropped">
          {error}
        </p>
      )}
    </form>
  )
}
