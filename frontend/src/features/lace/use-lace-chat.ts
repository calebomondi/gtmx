import { useCallback, useEffect, useRef, useState } from "react"

import {
  ApiError,
  followRunEvents,
  findLaceAccountContacts,
  getLace,
  deleteLaceOutreach,
  dismissLaceOpportunity,
  listActiveRuns,
  listLaceAccounts,
  listLaceCompetitors,
  listLaceFacts,
  listLaceMessages,
  listLaceOutreach,
  markLaceOutreachSent,
  sendLaceMessage,
  sendLaceOutreach,
  setLaceAccountStatus,
  setLaceCompetitorStatus,
  updateLaceOutreach,
  type FactDto,
  type LaceAccountDto,
  type LaceCompetitorDto,
  type LaceDto,
  type LaceMessageDto,
  type LaceOutreachDto,
  type LaceOutreachChanges,
  type RunFrame,
} from "@/lib/api"

import { waitsOnFounder } from "./outreach-threads"

const TERMINAL = new Set(["complete", "error", "cancelled"])
// How long the founder has to undo a send before the message goes out.
export const UNDO_SEND_MS = 5_000
// How often an idle page looks for work the Lace started on its own, such as
// a turn reporting a finished competitor search.
const IDLE_POLL_MS = 15_000

export interface LaceChat {
  lace: LaceDto | null
  messages: LaceMessageDto[]
  facts: FactDto[]
  competitors: LaceCompetitorDto[]
  /** A background competitor search is running. */
  searching: boolean
  accounts: LaceAccountDto[]
  /** A background search for target accounts, or for their contacts, is running. */
  findingAccounts: boolean
  outreach: LaceOutreachDto[]
  /** Messages waiting on the founder: drafts to send, and replies not yet read. */
  waiting: number
  /** The Lace is drafting messages in the background. */
  drafting: boolean
  /** The Lace is looking for opportunities in the background. */
  findingOpportunities: boolean
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
  dismissCompetitor: (competitorId: string) => Promise<void>
  dismissAccount: (accountId: string) => Promise<void>
  saveDraft: (messageId: string, changes: LaceOutreachChanges) => Promise<void>
  discardDraft: (messageId: string) => Promise<void>
  /** Send a draft (the founder's approval) after UNDO_SEND_MS, unless undone. */
  sendDraft: (messageId: string) => void
  /** Drafts counting down to being sent. */
  sendingSoon: ReadonlySet<string>
  undoSend: (messageId: string) => void
  markSent: (messageId: string) => Promise<void>
  /** Look for who to contact at one account, in the background. */
  findContacts: (accountId: string) => Promise<void>
  /** "Not for us": the opportunity leaves the Lace's list. True when done. */
  dismissOpportunity: (opportunityId: string) => Promise<boolean>
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** One Lace's conversation, what it knows, and the run it is working on. The
 * server is the source of truth: when a run ends, everything is refetched
 * rather than pieced together from frames. State is per Lace: render the user
 * under a `key` of the Lace id. */
export function useLaceChat(laceId: string): LaceChat {
  const [lace, setLace] = useState<LaceDto | null>(null)
  const [messages, setMessages] = useState<LaceMessageDto[]>([])
  const [facts, setFacts] = useState<FactDto[]>([])
  const [competitors, setCompetitors] = useState<LaceCompetitorDto[]>([])
  const [searching, setSearching] = useState(false)
  const [accounts, setAccounts] = useState<LaceAccountDto[]>([])
  const [findingAccounts, setFindingAccounts] = useState(false)
  const [outreach, setOutreach] = useState<LaceOutreachDto[]>([])
  const [drafting, setDrafting] = useState(false)
  const [findingOpportunities, setFindingOpportunities] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [working, setWorking] = useState(false)
  const [step, setStep] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const abort = useRef<AbortController | null>(null)
  // Mirrors `working` for callbacks; written only from them, never in render.
  const busy = useRef(false)

  const refresh = useCallback(async () => {
    const [nextLace, nextMessages, nextFacts, nextCompetitors, nextAccounts, nextOutreach] = await Promise.all([
      getLace(laceId), listLaceMessages(laceId), listLaceFacts(laceId), listLaceCompetitors(laceId),
      listLaceAccounts(laceId), listLaceOutreach(laceId),
    ])
    setLace(nextLace)
    setMessages(nextMessages)
    setFacts(nextFacts)
    setCompetitors(nextCompetitors)
    setAccounts(nextAccounts)
    setOutreach(nextOutreach)
  }, [laceId])

  const follow = useCallback(async (runId: string) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    busy.current = true
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
    try {
      await refresh()
    } catch (err) {
      setError(message(err))
    }
    busy.current = false
    setDraft("")
    setStep(null)
    setWorking(false)
  }, [refresh])

  const checkRuns = useCallback(async () => {
    const mine = (await listActiveRuns()).filter((run) => run.lace_id === laceId)
    setSearching(mine.some((run) => run.kind === "lace_competitors"))
    setFindingAccounts(mine.some((run) => run.kind === "lace_accounts" || run.kind === "lace_contacts"))
    setDrafting(mine.some((run) => run.kind === "lace_drafts"))
    setFindingOpportunities(mine.some((run) => run.kind === "lace_opportunities"))
    const turn = mine.find((run) => run.kind === "lace_turn" || run.kind === "lace_onboarding")
    if (turn && !busy.current) void follow(turn.id)
  }, [laceId, follow])

  useEffect(() => {
    let cancelled = false
    refresh()
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
      abort.current?.abort()
    }
  }, [refresh])

  // Whenever the Lace is idle: look now (a run may have just ended and the
  // Lace gone straight on to pass along an update), then every so often.
  useEffect(() => {
    if (working) return
    // A missed check is retried on the next tick.
    const check = () => void checkRuns().catch(() => undefined)
    check()
    const timer = setInterval(check, IDLE_POLL_MS)
    return () => clearInterval(timer)
  }, [working, checkRuns])

  const dismissCompetitor = useCallback(async (competitorId: string) => {
    try {
      await setLaceCompetitorStatus(laceId, competitorId, "dismissed")
      setCompetitors((prev) => prev.filter((c) => c.id !== competitorId))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const dismissAccount = useCallback(async (accountId: string) => {
    try {
      await setLaceAccountStatus(laceId, accountId, "dismissed")
      setAccounts((prev) => prev.filter((a) => a.id !== accountId))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const saveDraft = useCallback(async (messageId: string, changes: LaceOutreachChanges) => {
    try {
      const saved = await updateLaceOutreach(laceId, messageId, changes)
      setOutreach((prev) => prev.map((m) => (m.id === messageId ? saved : m)))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const discardDraft = useCallback(async (messageId: string) => {
    try {
      await deleteLaceOutreach(laceId, messageId)
      setOutreach((prev) => prev.filter((m) => m.id !== messageId))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const replaceOutreach = useCallback(async (messageId: string, action: typeof sendLaceOutreach) => {
    try {
      const updated = await action(laceId, messageId)
      setOutreach((prev) => prev.map((m) => (m.id === messageId ? updated : m)))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])
  // Sends waiting out their undo window: message id -> timer.
  const pendingSends = useRef(new Map<string, number>())
  const [sendingSoon, setSendingSoon] = useState<ReadonlySet<string>>(new Set())
  const settle = useCallback((messageId: string) => {
    window.clearTimeout(pendingSends.current.get(messageId))
    pendingSends.current.delete(messageId)
    setSendingSoon(new Set(pendingSends.current.keys()))
  }, [])
  const sendDraft = useCallback((messageId: string) => {
    if (pendingSends.current.has(messageId)) return
    pendingSends.current.set(messageId, window.setTimeout(() => {
      settle(messageId)
      void replaceOutreach(messageId, sendLaceOutreach)
    }, UNDO_SEND_MS))
    setSendingSoon(new Set(pendingSends.current.keys()))
  }, [replaceOutreach, settle])
  const undoSend = useCallback((messageId: string) => settle(messageId), [settle])
  // Leaving the Lace mid-countdown sends at once: the founder meant to send.
  useEffect(() => {
    const pending = pendingSends.current
    return () => {
      for (const [messageId, timer] of pending) {
        window.clearTimeout(timer)
        void sendLaceOutreach(laceId, messageId).catch(() => undefined) // the draft stays a draft
      }
      pending.clear()
    }
  }, [laceId])
  const markSent = useCallback((messageId: string) => replaceOutreach(messageId, markLaceOutreachSent), [replaceOutreach])

  const dismissOpportunity = useCallback(async (opportunityId: string) => {
    try {
      await dismissLaceOpportunity(laceId, opportunityId)
      return true
    } catch (err) {
      setError(message(err))
      return false
    }
  }, [laceId])

  const findContacts = useCallback(async (accountId: string) => {
    try {
      await findLaceAccountContacts(laceId, accountId)
      await checkRuns()
    } catch (err) {
      setError(message(err))
    }
  }, [laceId, checkRuns])

  const send = useCallback(async (text: string) => {
    setError(null)
    setMessages((prev) => [...prev, { role: "founder", content: text }])
    try {
      const { run_id } = await sendLaceMessage(laceId, text)
      await follow(run_id)
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? "Your Lace is still working on the last message." : message(err))
      await refresh().catch(() => undefined)  // the send error is already shown
    }
  }, [laceId, follow, refresh])

  const waiting = outreach.filter(waitsOnFounder).length

  return {
    lace, messages, facts, competitors, searching, accounts, findingAccounts, outreach, waiting, drafting, findingOpportunities,
    loading, error,
    working, step, draft, send, dismissCompetitor, dismissAccount, saveDraft, discardDraft, sendDraft, sendingSoon,
    undoSend, markSent, findContacts, dismissOpportunity,
  }
}
