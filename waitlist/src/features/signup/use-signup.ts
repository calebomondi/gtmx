import { useState } from 'react'

import { ApiError, joinWaitlist, saveDetails, type WaitlistDetails } from '../../lib/api'
import { readSource } from '../../lib/source'

export type SignupStep = 'email' | 'details' | 'done'

/** The two-step signup: the email puts them on the list at once; the details
 * (all optional) follow in place, and can be skipped. */
export function useSignup(onPilotSpotsLeft: (left: number) => void) {
  const [step, setStep] = useState<SignupStep>('email')
  const [token, setToken] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [wantsPilot, setWantsPilot] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async (work: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await work()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const join = (address: string, nickname: string) =>
    run(async () => {
      const joined = await joinWaitlist(address.trim(), readSource(), nickname)
      setEmail(address.trim())
      setToken(joined.token)
      onPilotSpotsLeft(joined.pilot_spots_left)
      setStep('details')
    })

  const save = (details: WaitlistDetails) =>
    run(async () => {
      if (!token) return
      const saved = await saveDetails(token, details)
      setWantsPilot(saved.wants_pilot)
      onPilotSpotsLeft(saved.pilot_spots_left)
      setStep('done')
    })

  const skip = () => setStep('done')

  return { step, email, wantsPilot, busy, error, join, save, skip }
}
