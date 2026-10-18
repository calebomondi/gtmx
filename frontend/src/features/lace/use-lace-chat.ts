import { useCallback, useEffect, useRef, useState } from "react"

import {
  ApiError,
  followRunEvents,
  getLace,
  listActiveRuns,
  listLaceFacts,
  listLaceMessages,
  sendLaceMessage,
  type FactDto,
  type LaceDto,
  type LaceMessageDto,
  type RunFrame,
} from "@/lib/api"

const TERMINAL = new Set(["complete", "error", "cancelled"])

export interface LaceChat {
  lace: LaceDto | null
  messages: LaceMessageDto[]
  facts: FactDto[]
  loading: boolean
  /** A load or send failure, or a run that failed. */
  error: string | null
  /** True while the Lace is working on a run (onboarding or a turn). */
  working: boolean
  /** What the Lace is doing right now, e.g. "Reading https://…/pricing". */
  step: string | null
  /** The reply as it is being written; empty when nothing is streaming. */
  draft: string
  send: (text: string) => Promise<void>
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** One Lace's conversation, its facts, and the run it is working on. The
 * server is the source of truth: when a run ends, the conversation and facts
 * are refetched rather than pieced together from frames. State is per Lace:
 * render the user under a `key` of the Lace id. */
export function useLaceChat(laceId: string): LaceChat {
  const [lace, setLace] = useState<LaceDto | null>(null)
  const [messages, setMessages] = useState<LaceMessageDto[]>([])
  const [facts, setFacts] = useState<FactDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [working, setWorking] = useState(false)
  const [step, setStep] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const abort = useRef<AbortController | null>(null)

  const refresh = useCallback(async () => {
    const [nextLace, nextMessages, nextFacts] = await Promise.all([
      getLace(laceId), listLaceMessages(laceId), listLaceFacts(laceId),
    ])
    setLace(nextLace)
    setMessages(nextMessages)
    setFacts(nextFacts)
  }, [laceId])

  const follow = useCallback(async (runId: string) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setWorking(true)
    setStep(null)
    const onFrame = (frame: RunFrame) => {
      if (frame.type === "token" && frame.text) setDraft((prev) => prev + frame.text)
      if (frame.type === "token_reset") setDraft("")
      if (frame.type === "step" && frame.text) {
        setStep(frame.text)
        setDraft("")
      }
      if (frame.type === "error" || frame.type === "cancelled") setError(frame.message ?? "The run stopped.")
    }
    try {
      await followRunEvents(runId, (frame) => {
        onFrame(frame)
        if (TERMINAL.has(frame.type)) controller.abort()
      }, { signal: controller.signal })
    } catch (err) {
      if (!controller.signal.aborted) setError(message(err))
    }
    if (abort.current !== controller) return  // a newer run took over
    setWorking(false)
    setStep(null)
    try {
      await refresh()
      setDraft("")
    } catch (err) {
      setError(message(err))
    }
  }, [refresh])

  useEffect(() => {
    let cancelled = false
    Promise.all([refresh(), listActiveRuns()])
      .then(([, runs]) => {
        if (cancelled) return
        const active = runs.find((run) => run.lace_id === laceId)
        if (active) void follow(active.id)
      })
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
      abort.current?.abort()
    }
  }, [laceId, refresh, follow])

  const send = useCallback(async (text: string) => {
    setError(null)
    setMessages((prev) => [...prev, { role: "founder", content: text }])
    try {
      const { run_id } = await sendLaceMessage(laceId, text)
      await follow(run_id)
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? "Your Lace is still working on the last message." : message(err))
      await refresh().catch(() => undefined)
    }
  }, [laceId, follow, refresh])

  return { lace, messages, facts, loading, error, working, step, draft, send }
}
