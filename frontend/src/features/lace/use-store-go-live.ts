import { useCallback, useState } from "react"

import {
  getStoreSignature, requestStoreSignature, setStoreOwner, submitStoreSignature,
  type SignatureStatusDto, type StoreDto, type StoreSignatureType,
} from "@/lib/api"

import { createStorePasskey, passkeyError, signWithPasskey } from "./store-passkey"

/** Where going live stands, for the button and the line under it. */
export type GoLivePhase = "idle" | "passkey" | "signing" | "waiting" | "live" | "failed"

export const SIGNATURE_LABEL: Record<StoreSignatureType, string> = {
  agent_create: "Opening the Store's wallet under your rules",
  grant_issue: "Letting your Lace act inside those rules",
  policy_update: "Changing the rules",
  agent_freeze: "Freezing the wallet",
  agent_unfreeze: "Unfreezing the wallet",
}

// A submitted request usually settles in seconds; NEAR can take longer.
const POLL_EVERY_MS = 3_000
const POLL_FOR_MS = 120_000

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

async function settled(laceId: string, first: SignatureStatusDto): Promise<SignatureStatusDto> {
  let current = first
  const deadline = Date.now() + POLL_FOR_MS
  while (current.status === "submitted" && Date.now() < deadline) {
    await wait(POLL_EVERY_MS)
    current = await getStoreSignature(laceId, current.correlation_id)
  }
  return current
}

export interface StoreGoLive {
  phase: GoLivePhase
  /** The signature being made or waited on. */
  step: StoreSignatureType | null
  error: string | null
  start: () => Promise<void>
}

/** Take the Store live: make the owner's passkey if there isn't one, then
 * sign each request NEAR Intents needs (opening the wallet, then letting
 * the Lace act) and wait for it to settle. */
export function useStoreGoLive(laceId: string, store: StoreDto | null, who: { email: string; name: string },
                               onStore: (store: StoreDto) => void): StoreGoLive {
  const [phase, setPhase] = useState<GoLivePhase>("idle")
  const [step, setStep] = useState<StoreSignatureType | null>(null)
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(async () => {
    if (!store) return
    setError(null)
    try {
      let current = store
      if (!current.has_owner) {
        setPhase("passkey")
        current = await setStoreOwner(laceId, await createStorePasskey(current.name, who))
        onStore(current)
      }
      while (current.status !== "live") {
        setPhase("signing")
        const request = await requestStoreSignature(laceId)
        setStep(request.type)
        const signed = await signWithPasskey(request)
        setPhase("waiting")
        const done = await settled(laceId, await submitStoreSignature(laceId, request.correlation_id, signed))
        if (done.status === "submitted") throw new Error("NEAR is taking longer than usual. Check back in a few minutes.")
        if (done.status !== "succeeded") throw new Error(`NEAR Intents didn't accept it (${done.failure_code ?? done.status}).`)
        current = done.store
        onStore(current)
      }
      setPhase("live")
      setStep(null)
    } catch (err) {
      setError(passkeyError(err))
      setPhase("failed")
    }
  }, [laceId, store, who, onStore])

  return { phase, step, error, start }
}
