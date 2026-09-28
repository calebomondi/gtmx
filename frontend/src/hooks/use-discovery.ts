import { useCallback } from "react"

import type { DiscoveryInterruptFrame, DiscoveryRequest, OfferSnapshot } from "@/lib/api"
import {
  answerDiscovery,
  resetDiscovery,
  startDiscovery,
  useAgentRun,
  type DiscoveryStage,
} from "@/lib/agent-run-store"

export type { DiscoveryStage }

export interface DiscoveryController {
  stage: DiscoveryStage
  currentInterrupt: DiscoveryInterruptFrame | null
  snapshot: OfferSnapshot | null
  sessionId: string | null
  workspaceId: string | null
  error: string | null
  isRunning: boolean
  start: (request: DiscoveryRequest) => Promise<void>
  answer: (text: string) => void
  reset: () => void
}

/**
 * React binding over the module-level agent run store. The discovery socket
 * deliberately lives outside React so it keeps streaming after `/new`
 * unmounts and the user lands on `/workspace/:workspace_id`.
 */
export function useDiscovery(): DiscoveryController {
  const run = useAgentRun()

  const start = useCallback((request: DiscoveryRequest) => {
    return startDiscovery(request)
  }, [])

  const answer = useCallback((text: string) => {
    answerDiscovery(text)
  }, [])

  const reset = useCallback(() => {
    resetDiscovery()
  }, [])

  return {
    stage: run.stage,
    currentInterrupt: run.currentInterrupt,
    snapshot: run.snapshot,
    sessionId: run.sessionId,
    workspaceId: run.workspaceId,
    error: run.error,
    isRunning:
      run.stage === "connecting" ||
      run.stage === "awaiting_input" ||
      run.stage === "running",
    start,
    answer,
    reset,
  }
}
