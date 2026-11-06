import { useState } from 'react'

import { ApiError, joinWaitlist, saveDetails, type WaitlistDetails } from '../../lib/api'
import { readSource } from '../../lib/source'

export type SignupStep = 'email' | 'details' | 'done'

/** The two-step signup: the email (and the pilot choice) puts them on the
 * list at once; the details, all optional, follow and can be skipped. */
export function useSignup(onPilotSpotsLeft: (left: number) => void) {
  const [step, setStep] = useState<SignupStep>('email')
  const [token, setToken] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [wantsPilot, setWantsPilot] = useState(false)
  // Whether the server holds the pilot choice yet; skipping saves it if not.
  const [pilotSaved, setPilotSaved] = useState(false)
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

  const record = async (key: string, details: WaitlistDetails) => {
    const saved = await saveDetails(key, details)
    setWantsPilot(saved.wants_pilot)
    setPilotSaved(true)
    onPilotSpotsLeft(saved.pilot_spots_left)
  }

  const join = (address: string, nickname: string, pilot: boolean) =>
    run(async () => {
      const joined = await joinWaitlist(address.trim(), readSource(), nickname)
      setEmail(address.trim())
      setToken(joined.token)
      setWantsPilot(pilot)
      onPilotSpotsLeft(joined.pilot_spots_left)
      // The pilot is asked for on the first step, so it's kept even if they
      // close the details. They're on the list already: a failure here is
      // retried when they save or skip, not shown as a failed join.
      if (pilot) await record(joined.token, { wants_pilot: true }).catch(() => undefined)
      setStep('details')
    })

  const save = (details: WaitlistDetails) =>
    run(async () => {
      if (!token) return
      await record(token, details)
      setStep('done')
    })

  const skip = () =>
    run(async () => {
      if (token && wantsPilot && !pilotSaved) await record(token, { wants_pilot: true })
      setStep('done')
    })

  return { step, email, wantsPilot, busy, error, join, save, skip }
}
