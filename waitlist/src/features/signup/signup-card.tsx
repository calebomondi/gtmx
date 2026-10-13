import type { PilotSpots } from '../../lib/api'
import { DetailsStep } from './details-step'
import { DoneStep } from './done-step'
import { EmailStep } from './email-step'
import { useSignup } from './use-signup'

/** The signup, in place: email first, then the optional details, then done. */
export function SignupCard({ pilot, onPilotSpotsLeft }: { pilot: PilotSpots | null; onPilotSpotsLeft: (left: number) => void }) {
  const signup = useSignup(onPilotSpotsLeft)
  return (
    <div id="join" className="scroll-mt-24">
      {signup.step === 'email' && <EmailStep busy={signup.busy} error={signup.error} onJoin={signup.join} />}
      {signup.step === 'details' && (
        <div className="rounded-xl border border-line bg-panel p-5 shadow-sm sm:p-6">
          <DetailsStep
            email={signup.email}
            pilot={pilot}
            busy={signup.busy}
            error={signup.error}
            onSave={signup.save}
            onSkip={signup.skip}
          />
        </div>
      )}
      {signup.step === 'done' && (
        <div className="rounded-xl border border-line bg-panel p-5 sm:p-6">
          <DoneStep email={signup.email} wantsPilot={signup.wantsPilot} />
        </div>
      )}
    </div>
  )
}
