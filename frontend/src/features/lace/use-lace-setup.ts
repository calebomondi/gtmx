import { useCallback, useEffect, useState } from "react"

import {
  correctLaceFact,
  followRunEvents,
  getLace,
  listActiveRuns,
  listLaceFacts,
  reviewLaceFact,
  type FactDto,
  type FactVerdict,
  type LaceDto,
  type RunFrame,
} from "@/lib/api"
import { refetchLaces } from "@/lib/laces-store"

/** printing: onboarding is reading the site. waking: the print is done and
 * the mascot opens its eyes. review: the founder checks what it learned.
 * unreadable: the site could not be read. failed: onboarding stopped. */
export type SetupPhase = "printing" | "waking" | "review" | "unreadable" | "failed"

// How long the finished mascot takes to wake before the review shows.
const WAKE_MS = 1_400

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

async function onboardingRun(laceId: string): Promise<string | null> {
  const runs = await listActiveRuns()
  return runs.find((run) => run.lace_id === laceId && run.kind === "lace_onboarding")?.id ?? null
}

/** A new Lace's creation: follows its onboarding run (`runId`, or the active
 * one), then loads what it learned for the founder to confirm, retract or
 * correct. A Lace that finished onboarding earlier goes straight to review. */
export function useLaceSetup(laceId: string, runId: string | null) {
  const [phase, setPhase] = useState<SetupPhase>("printing")
  const [progress, setProgress] = useState(0)
  const [step, setStep] = useState("Getting ready")
  const [lace, setLace] = useState<LaceDto | null>(null)
  const [facts, setFacts] = useState<FactDto[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let unreadable = false
    let wake: number | undefined

    const toReview = async () => {
      const [nextLace, nextFacts] = await Promise.all([getLace(laceId), listLaceFacts(laceId)])
      if (controller.signal.aborted) return
      setLace(nextLace)
      setFacts(nextFacts)
      setPhase(unreadable ? "unreadable" : "review")
      void refetchLaces()
    }
    const onFrame = (frame: RunFrame) => {
      if (frame.type === "progress" && frame.fraction !== undefined) {
        const fraction = frame.fraction
        setProgress((prev) => Math.max(prev, fraction))
        if (frame.text) setStep(frame.text)
      }
      if (frame.type === "onboarded") unreadable = (frame.pages_read ?? []).length === 0
      if (frame.type === "error" || frame.type === "cancelled") {
        setError(frame.message ?? "Your Lace stopped before it finished.")
        setPhase("failed")
      }
      if (frame.type === "complete") {
        setProgress(1)
        setPhase("waking")
        wake = window.setTimeout(() => void toReview().catch((err) => setError(message(err))), WAKE_MS)
      }
    }

    void (async () => {
      setLace(await getLace(laceId))
      const run = runId ?? (await onboardingRun(laceId))
      if (run) {
        await followRunEvents(run, onFrame, { signal: controller.signal })
      } else {
        // Onboarding finished before this page opened.
        setProgress(1)
        await toReview()
      }
    })().catch((err) => {
      if (controller.signal.aborted) return
      setError(message(err))
      setPhase("failed")
    })
    return () => {
      controller.abort()
      window.clearTimeout(wake)
    }
  }, [laceId, runId])

  const review = useCallback(async (factId: string, verdict: FactVerdict) => {
    setError(null)
    try {
      const updated = await reviewLaceFact(laceId, factId, verdict)
      setFacts((prev) => verdict === "retracted"
        ? prev.filter((f) => f.id !== factId)
        : prev.map((f) => (f.id === factId ? updated : f)))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const correct = useCallback(async (factId: string, claim: string) => {
    setError(null)
    try {
      const replacement = await correctLaceFact(laceId, factId, claim)
      setFacts((prev) => prev.map((f) => (f.id === factId ? replacement : f)))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  return { phase, progress, step, lace, facts, error, review, correct }
}
