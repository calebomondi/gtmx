import { useSyncExternalStore } from "react"

import {
  DiscoveryClient,
  DiscoveryConnectionError,
  type AgentNode,
  type DiscoveryInterruptFrame,
  type DiscoveryPhaseDataFrame,
  type DiscoveryRequest,
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
  create_specialists?: import("@/lib/api").SpecialistTeamDto
  understand_product?: string
  understand_market?: {
    market_data: NonNullable<
      Extract<
        DiscoveryPhaseDataFrame,
        { node: "understand_market" }
      >["market_data"]
    >
    product_market_fit_understanding: string | null
  }
  understand_competition?: Extract<
    DiscoveryPhaseDataFrame,
    { node: "understand_competition" }
  >["competition_data"]
  determine_icp?: Extract<
    DiscoveryPhaseDataFrame,
    { node: "determine_icp" }
  >["icp"]
}

export interface AgentRunState {
  stage: DiscoveryStage
  sessionId: string | null
  workspaceId: string | null
  currentInterrupt: DiscoveryInterruptFrame | null
  snapshot: OfferSnapshot | null
  confirmed: boolean
  userReplies: string[]
  error: string | null
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
  phases: {},
  phaseResults: {},
}

let state: AgentRunState = initialState
let client: DiscoveryClient | null = null
let pendingConnect: AbortController | null = null
let cancelled = false
let answerResolver: ((answer: string) => void) | null = null

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

function teardown(): void {
  cancelled = true
  answerResolver?.("")
  answerResolver = null
  client?.close()
  client = null
  // A connect() still inside its 15s window has not been assigned to `client`
  // yet, so closing `client` above misses it entirely. Abort it explicitly --
  // otherwise cancelling and immediately retrying leaves the orphaned socket
  // parked in CONNECTING, stacking one attempt per click against the origin's
  // connection pool until nothing else can connect.
  pendingConnect?.abort()
  pendingConnect = null
}

async function run(activeClient: DiscoveryClient): Promise<void> {
  try {
    for await (const frame of activeClient) {
      if (cancelled) return

      switch (frame.type) {
        case "interrupt": {
          setState({
            stage: "awaiting_input",
            error: null,
            sessionId: frame.session_id,
            currentInterrupt: frame,
          })
          const reply = await new Promise<string>((resolve) => {
            answerResolver = resolve
          })
          answerResolver = null
          if (cancelled || !reply) return
          activeClient.send(JSON.stringify({ answer: reply }))
          setState({ stage: "running", currentInterrupt: null })
          break
        }
        case "workspace_created":
          setState({
            sessionId: frame.session_id,
            workspaceId: frame.workspace_id,
            currentInterrupt: null,
            stage: "running",
          })
          void refetchWorkspaces()
          break
        case "phase":
          setState({
            phases: { ...state.phases, [frame.node]: frame.status },
          })
          break
        case "phase_data":
          applyPhaseData(frame)
          break
        case "complete": {
          const completedWorkspaceId = frame.workspace_id ?? state.workspaceId
          setState({
            stage: "completed",
            sessionId: frame.session_id,
            workspaceId: completedWorkspaceId,
            currentInterrupt: null,
            snapshot: frame.offer_snapshot,
            confirmed: frame.confirmed,
            userReplies: frame.user_replies,
          })
          // The backend persists insights before emitting `complete`, so the
          // refetch lands on real data for the workspace tabs.
          if (completedWorkspaceId) void refreshInsights(completedWorkspaceId)
          return
        }
        case "error":
          setState({
            stage: "error",
            currentInterrupt: null,
            error: frame.message,
          })
          return
      }
    }
    if (!cancelled && state.stage !== "completed") {
      setState({
        stage: "error",
        currentInterrupt: null,
        error: "discovery ended unexpectedly",
      })
    }
  } catch (err) {
    if (cancelled) return
    setState({
      stage: "error",
      currentInterrupt: null,
      error: err instanceof Error ? err.message : String(err),
    })
  } finally {
    // Always release the socket. Returning early (complete / error / cancel) or
    // throwing out of the loop used to leave it open while `client` was nulled,
    // which defeated the "already in progress" guard above and stacked one
    // browser connection per attempt until the origin's socket pool was full.
    activeClient.close()
    client = null
  }
}

function applyPhaseData(frame: DiscoveryPhaseDataFrame): void {
  const results = { ...state.phaseResults }
  if (frame.node === "create_specialists") {
    results.create_specialists = frame.specialist_team
  } else if (frame.node === "understand_product") {
    results.understand_product = frame.product_domain_understanding
  } else if (frame.node === "understand_market") {
    results.understand_market = {
      market_data: frame.market_data,
      product_market_fit_understanding:
        frame.product_market_fit_understanding,
    }
  } else if (frame.node === "understand_competition") {
    results.understand_competition = frame.competition_data
  } else if (frame.node === "determine_icp") {
    results.determine_icp = frame.icp
  }
  setState({ phaseResults: results })
}

export async function startDiscovery(request: DiscoveryRequest): Promise<void> {
  // `pendingConnect` matters as much as `client` here: a run that is still
  // handshaking owns a socket, and admitting a second one would give us two
  // live discovery sessions for the same user.
  if (client || pendingConnect) {
    throw new Error("a discovery session is already in progress")
  }
  teardown()
  cancelled = false
  state = { ...initialState, stage: "connecting" }
  for (const listener of listeners) listener()

  const controller = new AbortController()
  pendingConnect = controller

  try {
    const activeClient = await DiscoveryClient.connect(request, {
      signal: controller.signal,
    })
    if (cancelled) {
      activeClient.close()
      return
    }
    client = activeClient
    void run(activeClient)
  } catch (err) {
    if (cancelled) return
    setState({
      stage: "error",
      error:
        err instanceof DiscoveryConnectionError || err instanceof Error
          ? err.message
          : String(err),
    })
  } finally {
    // Only release our own handle -- a retry may already have installed one.
    if (pendingConnect === controller) pendingConnect = null
  }
}

export function answerDiscovery(answer: string): void {
  const resolve = answerResolver
  answerResolver = null
  resolve?.(answer)
}

export function resetDiscovery(): void {
  teardown()
  state = initialState
  for (const listener of listeners) listener()
}
