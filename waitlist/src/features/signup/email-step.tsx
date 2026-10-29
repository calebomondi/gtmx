import { useId, useRef, useState, type FormEvent } from 'react'

/** Step one: just an email and consent. Everything else is optional, later. */
export function EmailStep({
  busy,
  error,
  onJoin,
}: {
  busy: boolean
  error: string | null
  onJoin: (email: string, nickname: string) => void
}) {
  // Unique per form: the signup appears twice on the page.
  const id = useId()
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [nickname, setNickname] = useState('')
  const [missing, setMissing] = useState<'email' | 'consent' | null>(null)
  const emailField = useRef<HTMLInputElement>(null)
  const consentBox = useRef<HTMLInputElement>(null)

  // The button always looks ready: what is missing is said under its field
  // on submit, rather than left for a greyed-out button to hint at.
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    if (!email.trim() || !emailField.current?.checkValidity()) {
      setMissing('email')
      emailField.current?.focus()
    } else if (!consent) {
      setMissing('consent')
      consentBox.current?.focus()
    } else {
      onJoin(email, nickname)
    }
  }

  // noValidate: the browser's own bubble would show before these inline errors.
  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3">
      <label htmlFor={`${id}-email`} className="text-sm font-medium">
        Work email
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          ref={emailField}
          id={`${id}-email`}
          type="email"
          required
          autoComplete="email"
          inputMode="email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            if (missing === 'email') setMissing(null)
          }}
          aria-invalid={missing === 'email'}
          aria-describedby={missing === 'email' ? `${id}-email-error` : undefined}
          className="h-12 w-full min-w-0 rounded-md border border-ink/20 bg-panel px-3.5 text-base outline-none transition focus:border-ink focus:ring-4 focus:ring-brand/40 sm:flex-1"
        />
        <button
          type="submit"
          disabled={busy}
          className="btn-primary h-12 shrink-0 px-5 text-sm"
        >
          {busy ? 'Joining…' : 'Join the waitlist'}
        </button>
      </div>
      {missing === 'email' && (
        <p id={`${id}-email-error`} role="alert" className="-mt-1 text-sm text-dropped">
          Enter your work email.
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
      <label className="flex cursor-pointer items-start gap-2.5 text-[13px] leading-snug text-muted">
        <input
          ref={consentBox}
          id={`${id}-consent`}
          type="checkbox"
          checked={consent}
          onChange={(e) => {
            setConsent(e.target.checked)
            if (missing === 'consent') setMissing(null)
          }}
          aria-invalid={missing === 'consent'}
          aria-describedby={missing === 'consent' ? `${id}-consent-error` : undefined}
          className="mt-0.5 size-4 shrink-0 cursor-pointer accent-ink"
        />
        <span>
          Thalace may email me about the waitlist and the pilot. I can ask to be removed, and my details
          deleted, at any time.
        </span>
      </label>
      {missing === 'consent' && (
        <p id={`${id}-consent-error`} role="alert" className="-mt-1 text-sm text-dropped">
          Tick the box so we can email you about your spot.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-dropped">
          {error}
        </p>
      )}
    </form>
  )
}
