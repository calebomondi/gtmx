/** The last word: what happens next, and nothing else to do. */
export function DoneStep({ email, wantsPilot }: { email: string; wantsPilot: boolean }) {
  return (
    <div className="flex flex-col gap-2" role="status">
      <p className="font-mono text-xs uppercase tracking-wider text-kept">Done</p>
      <h2 className="text-xl font-semibold text-balance">
        {wantsPilot ? "You're in line for the pilot." : "You're on the waitlist."}
      </h2>
      <p className="text-sm leading-relaxed text-muted">
        {wantsPilot
          ? `We'll email ${email} within two weeks to set up your account and a short kickoff call.`
          : `We'll email ${email} when GTMX opens. Want a pilot spot after all? Reply to our email with "pilot".`}
      </p>
    </div>
  )
}
