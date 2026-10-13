import { useState, type FormEvent } from 'react'

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
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [nickname, setNickname] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (email.trim() && consent && !busy) onJoin(email, nickname)
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label htmlFor="join-email" className="text-sm font-medium">
        Work email
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id="join-email"
          type="email"
          required
          autoComplete="email"
          inputMode="email"
          placeholder="you@company.co.ke"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="h-12 w-full min-w-0 rounded-md border border-line bg-panel px-3.5 text-base outline-none transition focus:border-ink sm:flex-1"
        />
        <button
          type="submit"
          disabled={busy || !consent || !email.trim()}
          className="h-12 shrink-0 cursor-pointer rounded-md bg-ink px-5 text-sm font-semibold text-paper transition hover:bg-ink/85 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? 'Joining…' : 'Join the waitlist'}
        </button>
      </div>
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
          id="join-consent"
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-0.5 size-4 shrink-0 cursor-pointer accent-ink"
        />
        <span>
          GTMX may email me about the waitlist and the pilot. I can ask to be removed at any time, and my
          details are handled under Kenya's Data Protection Act, Nigeria's NDPR and South Africa's POPIA.
        </span>
      </label>
      {error && (
        <p role="alert" className="text-sm text-dropped">
          {error}
        </p>
      )}
    </form>
  )
}
