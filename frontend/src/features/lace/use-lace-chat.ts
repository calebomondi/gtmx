import { useCallback, useEffect, useRef, useState } from "react"

import {
  ApiError,
  answerLaceQuestion,
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
  listLaceActivity,
  listLaceAccounts,
  listLaceCompetitors,
  listLaceFacts,
  listLaceMessages,
  listLaceOutreach,
  markLaceOutreachRead,
  markLaceOutreachSent,
  sendLaceMessage,
  uploadLaceDocument,
  draftToLaceContact,
  sendLaceOutreach,
  setLaceAccountStatus,
  setLaceCompetitorStatus,
  updateLaceOutreach,
  type BlockAnswerDto,
  type FactDto,
  type LaceAccountDto,
  type LaceCompetitorDto,
  type LaceDto,
  type LaceMessageDto,
  type LaceOutreachDto,
  type LaceOutreachChanges,
  type OutreachChannel,
  type QuestionBlockDto,
  type RunDto,
  type RunFrame,
} from "@/lib/api"

import { waitsOnFounder } from "./outreach-threads"
import { answerLine } from "./questions"

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
  /** Everything it has done this turn, oldest first; the last is `step`. */
  steps: string[]
  /** Its background jobs running now (searches, drafting), oldest first. */
  jobs: RunDto[]
  /** The reply as it is being written; empty when nothing is streaming. */
  draft: string
  /** Send a message, uploading `files` first and attaching them. */
  send: (text: string, files?: File[]) => Promise<void>
  /** Answer a question under the latest reply: a choice, checklist or form. */
  answer: (block: QuestionBlockDto, answer: BlockAnswerDto) => Promise<void>
  /** Load the Lace again (after it was archived or restored, or to retry a
   * failed load); a failure becomes `error`. */
  reload: () => Promise<void>
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
  /** The founder opened these replies: they stop counting as unread. */
  markRead: (messageIds: string[]) => void
  /** Look for who to contact at one account, in the background. */
  findContacts: (accountId: string) => Promise<void>
  /** Ask the Lace to draft to one person, on email or LinkedIn, with a note.
   * Resolves false (with `error` set) when it could not start. */
  draftToContact: (contactId: string, channel: OutreachChannel, note: string) => Promise<boolean>
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
  const [steps, setSteps] = useState<string[]>([])
  const [jobs, setJobs] = useState<RunDto[]>([])
  const [draft, setDraft] = useState("")
  const abort = useRef<AbortController | null>(null)
  // What the last look saw: the background jobs running, and the newest
  // activity (undefined before the first look). A job ending or new activity
  // (a draft written, a reply synced) means the lists changed on the server.
  const seenJobs = useRef<Set<string>>(new Set())
  const newestActivity = useRef<string | null | undefined>(undefined)
  // Mirrors `working` for callbacks; written only from them, never in render.
  const busy = useRef(false)

  // Each part is kept as it loads: one list failing (a refused request, the
  // server restarting) must not cost the page the Lace's name or what it knows.
  // The first failure is rethrown for the caller to show.
  const refresh = useCallback(async () => {
    const [nextLace, nextMessages, nextFacts, nextCompetitors, nextSuggestedCompetitors, nextAccounts,
      nextSuggestedAccounts, nextOutreach, nextContacts] = await Promise.allSettled([
      getLace(laceId), listLaceMessages(laceId), listLaceFacts(laceId), listLaceCompetitors(laceId, "tracked"),
      listLaceCompetitors(laceId, "suggested"), listLaceAccounts(laceId, "target"),
      listLaceAccounts(laceId, "suggested"), listLaceOutreach(laceId), listLaceContacts(laceId),
    ])
    const keep = <T,>(result: PromiseSettledResult<T>, set: (value: T) => void) => {
      if (result.status === "fulfilled") set(result.value)
    }
    keep(nextLace, setLace)
    keep(nextMessages, setMessages)
    keep(nextFacts, setFacts)
    keep(nextCompetitors, setCompetitors)
    keep(nextSuggestedCompetitors, setSuggestedCompetitors)
    keep(nextAccounts, setAccounts)
    keep(nextSuggestedAccounts, setSuggestedAccounts)
    keep(nextOutreach, setOutreach)
    keep(nextContacts, setContacts)
    const failed = [nextLace, nextMessages, nextFacts, nextCompetitors, nextSuggestedCompetitors, nextAccounts,
      nextSuggestedAccounts, nextOutreach, nextContacts].find((result) => result.status === "rejected")
    if (failed) throw failed.reason
  }, [laceId])

  const follow = useCallback(async (runId: string) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    busy.current = true
    setWorking(true)
    setStep(null)
    setSteps([])
    const onFrame = (frame: RunFrame) => {
      if (frame.type === "token" && frame.text) setDraft((prev) => prev + frame.text)
      if (frame.type === "token_reset") setDraft("")
      if (frame.type === "step" && frame.text) {
        const text = frame.text
        setStep(text)
        setSteps((prev) => (prev[prev.length - 1] === text ? prev : [...prev, text]))
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
    setSteps([])
    setWorking(false)
  }, [refresh])

  const checkRuns = useCallback(async () => {
    const [runs, latest] = await Promise.all([
      listActiveRuns(),
      // A failed look at activity only skips this round's change check.
      listLaceActivity(laceId, undefined, 1).catch(() => null),
    ])
    const mine = runs.filter((run) => run.lace_id === laceId)
    setSearching(mine.some((run) => run.kind === "lace_competitors"))
    setFindingAccounts(mine.some((run) => ["lace_accounts", "lace_contacts", "lace_icp"].includes(run.kind)))
    setDrafting(mine.some((run) => run.kind === "lace_drafts"))
    setFindingOpportunities(mine.some((run) => run.kind === "lace_opportunities"))
    const isTurn = (run: RunDto) => run.kind === "lace_turn" || run.kind === "lace_onboarding"
    const jobs = mine.filter((run) => !isTurn(run))
    setJobs([...jobs].reverse())
    const running = new Set(jobs.map((run) => run.id))
    const jobEnded = [...seenJobs.current].some((id) => !running.has(id))
    seenJobs.current = running
    const newest = latest ? (latest[0]?.id ?? null) : newestActivity.current
    const reported = newestActivity.current !== undefined && newest !== newestActivity.current
    newestActivity.current = newest
    // Drafts and replies land without a turn the page follows: load them now.
    if (jobEnded || reported) void refresh().catch(() => undefined)
    const turn = mine.find(isTurn)
    if (turn && !busy.current) void follow(turn.id)
  }, [laceId, follow, refresh])

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

  // Look now whenever a turn starts or ends (one may have just ended and the
  // Lace gone straight on to pass along an update), then every so often, so
  // background jobs show while a turn runs too. A running turn is never
  // followed twice: checkRuns leaves it to the follow already under way.
  useEffect(() => {
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

  const markRead = useCallback((messageIds: string[]) => {
    if (messageIds.length === 0) return
    const ids = new Set(messageIds)
    const now = new Date().toISOString()
    setOutreach((prev) => prev.map((m) => (ids.has(m.id) && m.read_at === null ? { ...m, read_at: now } : m)))
    markLaceOutreachRead(laceId, messageIds).catch((err) => {
      setOutreach((prev) => prev.map((m) => (ids.has(m.id) && m.read_at === now ? { ...m, read_at: null } : m)))
      setError(message(err))
    })
  }, [laceId])

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

  const draftToContact = useCallback(async (contactId: string, channel: OutreachChannel, note: string) => {
    try {
      await draftToLaceContact(laceId, contactId, channel, note)
      // Asking cleared them for outreach.
      setContacts((prev) => prev.map((c) => (c.id === contactId && !c.approved_at
        ? { ...c, approved_at: new Date().toISOString() } : c)))
      await checkRuns()
      return true
    } catch (err) {
      setError(message(err))
      return false
    }
  }, [laceId, checkRuns])

  const send = useCallback(async (text: string, files: File[] = []) => {
    setError(null)
    setMessages((prev) => [...prev, {
      role: "founder", content: text,
      ...(files.length ? { documents: files.map((f) => ({ id: f.name, filename: f.name })) } : {}),
    }])
    const documentIds: string[] = []
    try {
      for (const file of files) {
        setWorking(true)
        setStep(`Reading ${file.name}`)
        documentIds.push((await uploadLaceDocument(laceId, file)).id)
      }
    } catch (err) {
      // Nothing was sent: say why the file was refused (too large, unreadable).
      setWorking(false)
      setStep(null)
      setError(message(err))
      await refresh().catch(() => undefined)
      return
    }
    try {
      const { run_id } = await sendLaceMessage(laceId, text, documentIds)
      await follow(run_id)
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? "Your Lace is still working on the last message." : message(err))
      await refresh().catch(() => undefined)  // the send error is already shown
    }
  }, [laceId, follow, refresh])

  const answer = useCallback(async (block: QuestionBlockDto, given: BlockAnswerDto) => {
    setError(null)
    setMessages((prev) => [...prev, { role: "founder", content: answerLine(block, given), answer: given }])
    try {
      const { run_id } = await answerLaceQuestion(laceId, given)
      await follow(run_id)
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? "That question was already answered." : message(err))
      await refresh().catch(() => undefined)  // the error is already shown
    }
  }, [laceId, follow, refresh])

  const reload = useCallback(async () => {
    setError(null)
    try {
      await refresh()
    } catch (err) {
      setError(message(err))
    }
  }, [refresh])

  const waiting = outreach.filter(waitsOnFounder).length

  return {
    lace, messages, facts, competitors, searching, accounts, findingAccounts, outreach, waiting, drafting, findingOpportunities,
    loading, error,
    working, step, steps, jobs, draft, send, answer, reload, dismissCompetitor, dismissAccount, saveDraft, discardDraft, sendDraft, sendingSoon,
    undoSend, markSent, markRead, findContacts, draftToContact, contacts, approveContact, approveAccountContacts, saveCompetitor, saveAccount, decideOpportunity, suggestedCompetitors,
    suggestedAccounts,
  }
}
