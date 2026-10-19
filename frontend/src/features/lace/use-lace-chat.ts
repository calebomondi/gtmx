import { useCallback, useEffect, useRef, useState } from "react"

import {
  ApiError,
  followRunEvents,
  findLaceAccountContacts,
  getLace,
  listLaceContacts,
  approveLaceAccountContacts,
  setLaceContactApproved,
  type ContactDto,
  deleteLaceOutreach,
  setLaceOpportunityStatus,
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
  /** Competitors a search found, waiting for the founder to save or dismiss. */
  suggestedCompetitors: LaceCompetitorDto[]
  /** A background competitor search is running. */
  searching: boolean
  accounts: LaceAccountDto[]
  /** Accounts a search found, waiting for the founder to save or dismiss. */
  suggestedAccounts: LaceAccountDto[]
  /** A background search for target accounts, or for their contacts, is running. */
  findingAccounts: boolean
  outreach: LaceOutreachDto[]
  /** The people found at saved accounts. */
  contacts: ContactDto[]
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
  /** Clear one person for outreach, or take it back. */
  approveContact: (contactId: string, approved: boolean) => Promise<void>
  /** Clear everyone at one account for outreach. */
  approveAccountContacts: (accountId: string) => Promise<void>
  saveCompetitor: (competitorId: string) => Promise<void>
  saveAccount: (accountId: string) => Promise<void>
  /** Save an opportunity (open) or drop it (dismissed). True when done. */
  decideOpportunity: (opportunityId: string, status: "open" | "dismissed") => Promise<boolean>
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
  const [suggestedCompetitors, setSuggestedCompetitors] = useState<LaceCompetitorDto[]>([])
  const [searching, setSearching] = useState(false)
  const [accounts, setAccounts] = useState<LaceAccountDto[]>([])
  const [suggestedAccounts, setSuggestedAccounts] = useState<LaceAccountDto[]>([])
  const [findingAccounts, setFindingAccounts] = useState(false)
  const [outreach, setOutreach] = useState<LaceOutreachDto[]>([])
  const [contacts, setContacts] = useState<ContactDto[]>([])
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
    const [nextLace, nextMessages, nextFacts, nextCompetitors, nextSuggestedCompetitors, nextAccounts,
      nextSuggestedAccounts, nextOutreach, nextContacts] = await Promise.all([
      getLace(laceId), listLaceMessages(laceId), listLaceFacts(laceId), listLaceCompetitors(laceId, "tracked"),
      listLaceCompetitors(laceId, "suggested"), listLaceAccounts(laceId, "target"),
      listLaceAccounts(laceId, "suggested"), listLaceOutreach(laceId), listLaceContacts(laceId),
    ])
    setLace(nextLace)
    setMessages(nextMessages)
    setFacts(nextFacts)
    setCompetitors(nextCompetitors)
    setSuggestedCompetitors(nextSuggestedCompetitors)
    setAccounts(nextAccounts)
    setSuggestedAccounts(nextSuggestedAccounts)
    setOutreach(nextOutreach)
    setContacts(nextContacts)
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

  // Saving moves an item from suggested to saved; dismissing drops it from both.
  const decideCompetitor = useCallback(async (competitorId: string, status: "tracked" | "dismissed") => {
    try {
      const updated = await setLaceCompetitorStatus(laceId, competitorId, status)
      setSuggestedCompetitors((prev) => prev.filter((c) => c.id !== competitorId))
      setCompetitors((prev) => status === "tracked"
        ? [updated, ...prev.filter((c) => c.id !== competitorId)]
        : prev.filter((c) => c.id !== competitorId))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])
  const dismissCompetitor = useCallback((id: string) => decideCompetitor(id, "dismissed"), [decideCompetitor])
  const saveCompetitor = useCallback((id: string) => decideCompetitor(id, "tracked"), [decideCompetitor])

  const decideAccount = useCallback(async (accountId: string, status: "target" | "dismissed") => {
    try {
      const updated = await setLaceAccountStatus(laceId, accountId, status)
      setSuggestedAccounts((prev) => prev.filter((a) => a.id !== accountId))
      setAccounts((prev) => status === "target"
        ? [...prev.filter((a) => a.id !== accountId), updated]
        : prev.filter((a) => a.id !== accountId))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])
  const dismissAccount = useCallback((id: string) => decideAccount(id, "dismissed"), [decideAccount])
  const saveAccount = useCallback((id: string) => decideAccount(id, "target"), [decideAccount])

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

  const approveContact = useCallback(async (contactId: string, approved: boolean) => {
    try {
      const updated = await setLaceContactApproved(laceId, contactId, approved)
      setContacts((prev) => prev.map((c) => (c.id === contactId ? updated : c)))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const approveAccountContacts = useCallback(async (accountId: string) => {
    try {
      await approveLaceAccountContacts(laceId, accountId)
      const now = new Date().toISOString()
      setContacts((prev) => prev.map((c) => (c.account_id === accountId && !c.approved_at ? { ...c, approved_at: now } : c)))
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const decideOpportunity = useCallback(async (opportunityId: string, status: "open" | "dismissed") => {
    try {
      await setLaceOpportunityStatus(laceId, opportunityId, status)
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
    undoSend, markSent, findContacts, contacts, approveContact, approveAccountContacts, saveCompetitor, saveAccount, decideOpportunity, suggestedCompetitors,
    suggestedAccounts,
  }
}
