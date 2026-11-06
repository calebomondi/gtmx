/** The last word: what happens next, and nothing else to do. `contactWithin`
 * is how soon the team writes ("24 hours"), unknown while the spots load. */
export function DoneStep({ email, wantsPilot, contactWithin }: {
  email: string
  wantsPilot: boolean
  contactWithin: string | null
}) {
  return (
    <div className="flex flex-col gap-2" role="status">
      <p className="flex items-center gap-1.5 text-sm font-semibold text-kept">
        <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
        Done
      </p>
      <h2 className="text-xl font-semibold text-balance">
        {wantsPilot ? "You're in line for the pilot." : "You're on the waitlist."}
      </h2>
      <p className="text-sm leading-relaxed text-muted">
        {wantsPilot
          ? `We'll email ${email} ${contactWithin ? `within ${contactWithin}` : 'soon'} to set up your account.`
          : `We'll email ${email} when Thalace opens. Want a pilot spot after all? Reply to our email with "pilot".`}
      </p>
    </div>
  )
}
