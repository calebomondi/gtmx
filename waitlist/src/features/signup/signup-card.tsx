import type { PilotSpots } from '../../lib/api'
import { DetailsDialog } from './details-dialog'
import { DetailsStep } from './details-step'
import { DoneStep } from './done-step'
import { EmailStep } from './email-step'
import { useSignup } from './use-signup'

/** The signup: the email in place, then the optional details in a window
 * over the page, then done, in place again. */
export function SignupCard({
  pilot,
  onPilotSpotsLeft,
  id,
}: {
  pilot: PilotSpots | null
  onPilotSpotsLeft: (left: number) => void
  /** The page's #join target sets this; only one form can carry it. */
  id?: string
}) {
  const signup = useSignup(onPilotSpotsLeft)
  return (
    <div id={id} className="scroll-mt-24">
      {signup.step === 'email' && (
        <EmailStep pilot={pilot} busy={signup.busy} error={signup.error} onJoin={signup.join} />
      )}
      {signup.step === 'details' && (
        <>
          <div className="rounded-xl border border-line bg-panel p-5 sm:p-6" role="status">
            <p className="text-sm font-semibold text-kept">On the list</p>
            <p className="mt-1 text-sm text-muted">You're in, {signup.email}.</p>
          </div>
          <DetailsDialog onSkip={signup.skip}>
            <DetailsStep
              email={signup.email}
              pilot={pilot}
              chosePilot={signup.wantsPilot}
              busy={signup.busy}
              error={signup.error}
              onSave={signup.save}
              onSkip={signup.skip}
            />
          </DetailsDialog>
        </>
      )}
      {signup.step === 'done' && (
        <div className="rounded-xl border border-kept/30 bg-kept-soft p-5 sm:p-6">
          <DoneStep email={signup.email} wantsPilot={signup.wantsPilot} contactWithin={pilot?.contact_within ?? null} />
        </div>
      )}
    </div>
  )
}
