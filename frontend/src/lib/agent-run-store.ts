import { useSyncExternalStore } from "react"

import {
  answerRun,
  cancelRun,
  DiscoveryClient,
  listActiveRuns,
  type AgentNode,
  type DiscoveryFrame,
  type DiscoveryInterruptFrame,
  type DiscoveryPhaseDataFrame,
  type DiscoveryRequest,
  type DiscoveryResume,
  type OfferSnapshot,
  type PhaseStatus,
} from "@/lib/api"
import { refetchWorkspaces } from "@/lib/workspaces-store"
import { refreshInsights } from "@/lib/insights-store"

export type DiscoveryStage =
  | "idle"
  | "connecting"
  | "awaiting_input"
  | "running"
  | "completed"
  | "error"

export type StepStatus = "pending" | "running" | "done"

export interface StepProgress {
  stepId: string
  status: StepStatus
}

export type PhaseResults = {
  create_specialists?: import("@/lib/api").SpecialistDto[]
  understand_offer?: string
  understand_market?: {
    market_data: NonNullable<
      Extract<
        DiscoveryPhaseDataFrame,
        { node: "understand_market" }
      >["market_data"]
    >
    product_market_fit_understanding: string | null
  }
  /** The competition stage's two outputs, kept as ONE object because they
   * always arrive on the same frame. `swod` is the offer-vs-standard judgment;
   * `profile` is the archetype construct that names no company. `profile` may be
   * null: the stage soft-fails its structured passes. */
  understand_competition?: {
    swod: Extract<
      DiscoveryPhaseDataFrame,
      { node: "understand_competition" }
    >["competition_data"]
    profile: Extract<
      DiscoveryPhaseDataFrame,
      { node: "understand_competition" }
    >["ideal_competitor_profile"]
  }
  determine_icp?: Extract<
    DiscoveryPhaseDataFrame,
    { node: "determine_icp" }
  >["icp_data"]
}

/**
 * Client state for the user's discovery run.
 *
 * The run lives on the server; this store only mirrors it. The socket
 * subscribes to the run's event log, so a dropped connection is retried with
 * backoff and a page reload reattaches (from localStorage, or from the server's
 * list of active runs on another device), replaying every frame to rebuild
 * this state. Answers go over the socket, or over REST when it is down.
 */
export interface AgentRunState {
  stage: DiscoveryStage
  /** The run id (named sessionId for the components that already read it). */
  sessionId: string | null
  workspaceId: string | null
  currentInterrupt: DiscoveryInterruptFrame | null
  snapshot: OfferSnapshot | null
  confirmed: boolean
  userReplies: string[]
  error: string | null
  /** The socket dropped and is being re-established; the run is unaffected. */
  reconnecting: boolean
  phases: Partial<Record<AgentNode, PhaseStatus>>
  phaseResults: PhaseResults
}

type Listener = () => void

const listeners = new Set<Listener>()

const initialState: AgentRunState = {
  stage: "idle",
  sessionId: null,
  workspaceId: null,
  currentInterrupt: null,
  snapshot: null,
  confirmed: false,
  userReplies: [],
  error: null,
  reconnecting: false,
  phases: {},
  phaseResults: {},
}

const STORAGE_KEY = "gtmx.discoveryRun"
const TERMINAL_FRAMES = new Set(["complete", "error", "cancelled"])
const MAX_RECONNECT_DELAY_MS = 15_000
const MAX_RECONNECT_ATTEMPTS = 12

let state: AgentRunState = initialState
let client: DiscoveryClient | null = null
let lastEventId = 0
// Bumped by every start/reattach/reset, so a stale loop or reconnect timer
// from an earlier run can tell it has been superseded and stop.
let generation = 0

function setState(patch: Partial<AgentRunState>): void {
  state = { ...state, ...patch }
  for (const listener of listeners) listener()
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): AgentRunState {
  return state
}

export function useAgentRun(): AgentRunState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

// Browser storage is a convenience (it can be unavailable or cleared); the
// server's active-run list is the fallback.
function remember(runId: string | null): void {
  try {
    if (runId) localStorage.setItem(STORAGE_KEY, JSON.stringify({ runId }))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // storage unavailable -- reattach falls back to the server
  }
}

function remembered(): string | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as { runId?: string }).runId ?? null : null
  } catch {
    return null
  }
}

function closeSocket(): void {
  client?.close()
  client = null
}

function applyFrame(frame: DiscoveryFrame): void {
  if (frame.event_id) lastEventId = Math.max(lastEventId, frame.event_id)
  switch (frame.type) {
    case "run":
      remember(frame.run_id)
      setState({ sessionId: frame.run_id })
      break
    case "interrupt":
      setState({ stage: "awaiting_input", error: null, currentInterrupt: frame })
      break
    case "answered":
      setState({
        stage: "running",
        currentInterrupt: null,
        userReplies: [...state.userReplies, frame.answer],
      })
      break
    case "workspace_created":
      setState({ workspaceId: frame.workspace_id, currentInterrupt: null, stage: "running" })
      void refetchWorkspaces()
      break
    case "phase":
      setState({ phases: { ...state.phases, [frame.node]: frame.status } })
      break
    case "phase_data":
      applyPhaseData(frame)
      break
    case "complete": {
      const workspaceId = frame.workspace_id ?? state.workspaceId
      setState({
        stage: "completed",
        workspaceId,
        currentInterrupt: null,
        snapshot: frame.offer_snapshot,
        confirmed: frame.confirmed,
        userReplies: frame.user_replies,
      })
      // Insights are persisted before `complete` is emitted.
      if (workspaceId) void refreshInsights(workspaceId)
      break
    }
    case "error":
    case "cancelled":
      setState({ stage: "error", currentInterrupt: null, error: frame.message })
      break
    case "notice":
      setState({ error: frame.message })
      break
  }
}

/** Open a socket for `opening` and follow it; on an unexpected drop, reattach
 * with backoff from the last event seen. */
async function follow(opening: DiscoveryRequest | DiscoveryResume, myGeneration: number): Promise<void> {
  let attempt = 0
  let next: DiscoveryRequest | DiscoveryResume = opening
  while (myGeneration === generation) {
    try {
      const activeClient = await DiscoveryClient.connect(next)
      if (myGeneration !== generation) {
        activeClient.close()
        return
      }
      client = activeClient
      attempt = 0
      setState({ reconnecting: false })
      for await (const frame of activeClient) {
        if (myGeneration !== generation) return
        applyFrame(frame)
        if (TERMINAL_FRAMES.has(frame.type)) {
          remember(null)
          return
        }
      }
    } catch {
      // fall through to reconnect
    } finally {
      if (myGeneration === generation) closeSocket()
    }
    if (myGeneration !== generation) return
    if (!state.sessionId) {
      // Never got as far as a run (bad request, auth) -- nothing to reattach.
      setState({ stage: "error", reconnecting: false, error: state.error ?? "Could not start discovery." })
      return
    }
    attempt += 1
    if (attempt > MAX_RECONNECT_ATTEMPTS) {
      setState({ stage: "error", reconnecting: false, error: "Lost connection to the server. Reload to reconnect." })
      return
    }
    setState({ reconnecting: true })
    await new Promise((resolve) => setTimeout(resolve, Math.min(1000 * 2 ** (attempt - 1), MAX_RECONNECT_DELAY_MS)))
    next = { resume: state.sessionId, after: lastEventId }
  }
}

function begin(stage: DiscoveryStage): number {
  generation += 1
  closeSocket()
  lastEventId = 0
  state = { ...initialState, stage }
  for (const listener of listeners) listener()
  return generation
}

function applyPhaseData(frame: DiscoveryPhaseDataFrame): void {
  const results = { ...state.phaseResults }
  if (frame.node === "create_specialists") {
    results.create_specialists = frame.specialists
  } else if (frame.node === "understand_offer") {
    results.understand_offer = frame.offer_domain_fit_understanding
  } else if (frame.node === "understand_market") {
    results.understand_market = {
      market_data: frame.market_data,
      product_market_fit_understanding:
        frame.product_market_fit_understanding,
    }
  } else if (frame.node === "understand_competition") {
    // Kept as one object so a consumer cannot read the SWOD without noticing the
    // profile is right there beside it -- they are the same stage's output and
    // the profile is the primary one.
    results.understand_competition = {
      swod: frame.competition_data,
      profile: frame.ideal_competitor_profile,
    }
  } else if (frame.node === "determine_icp") {
    results.determine_icp = frame.icp_data
  }
  setState({ phaseResults: results })
}

export async function startDiscovery(request: DiscoveryRequest): Promise<void> {
  if (state.stage === "connecting" || state.stage === "running" || state.stage === "awaiting_input") {
    throw new Error("a discovery session is already in progress")
  }
  await follow(request, begin("connecting"))
}

/** Reattach to the user's unfinished discovery run, if any. Safe to call on
 * every app load; a no-op while a run is already being followed. */
export async function resumeActiveDiscovery(): Promise<void> {
  if (state.stage !== "idle") return
  let runId = remembered()
  if (!runId) {
    try {
      runId = (await listActiveRuns()).find((run) => run.kind === "discovery")?.id ?? null
    } catch {
      return
    }
  }
  if (!runId || state.stage !== "idle") return
  const myGeneration = begin("connecting")
  setState({ sessionId: runId })
  await follow({ resume: runId, after: 0 }, myGeneration)
  const after = getSnapshot() // re-read: `follow` mutated the store
  if (after.stage === "error" && myGeneration === generation && !after.workspaceId) {
    // The stored run is gone (not found / not ours): forget it quietly.
    remember(null)
    begin("idle")
  }
}

export function answerDiscovery(answer: string): void {
  const runId = state.sessionId
  const text = answer.trim()
  if (!runId || !text) return
  setState({ stage: "running", currentInterrupt: null })
  if (client?.isOpen) {
    client.send(JSON.stringify({ answer: text }))
  } else {
    answerRun(runId, text).catch((err) =>
      setState({ error: err instanceof Error ? err.message : String(err) }),
    )
  }
}

/** Stop following the run. A run still in progress is cancelled on the server
 * -- otherwise it would keep running (and spending) with nobody watching. */
export function resetDiscovery(): void {
  const runId = state.sessionId
  const live = state.stage === "connecting" || state.stage === "running" || state.stage === "awaiting_input"
  if (runId && live) void cancelRun(runId).catch(() => undefined)
  remember(null)
  begin("idle")
}
