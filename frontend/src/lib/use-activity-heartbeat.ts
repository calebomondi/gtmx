import { useEffect, useRef } from "react"
import { useMatches } from "react-router-dom"

import { sendHeartbeat } from "@/lib/api"

const DEFAULT_BEAT_S = 60
const INPUT_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart", "mousemove"] as const

function isActive(lastInputAt: number, beatS: number): boolean {
  // Idle for two beats, or the tab in the background, isn't time in the app.
  return document.visibilityState === "visible" && Date.now() - lastInputAt < 2 * beatS * 1000
}

/** Pings the API while the signed-in user is actively using the app, so the
 * admin console can report time in app and per workspace. Durations only. */
export function useActivityHeartbeat(enabled: boolean) {
  const workspaceId =
    useMatches()
      .map((m) => m.params.workspace_id)
      .find(Boolean) ?? null
  const lastInputAt = useRef(0)
  const beatS = useRef(DEFAULT_BEAT_S)

  useEffect(() => {
    if (!enabled) return
    const touch = () => {
      lastInputAt.current = Date.now()
    }
    INPUT_EVENTS.forEach((e) => window.addEventListener(e, touch, { passive: true }))
    return () => INPUT_EVENTS.forEach((e) => window.removeEventListener(e, touch))
  }, [enabled])

  useEffect(() => {
    if (!enabled) return
    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false
    const beat = async () => {
      if (isActive(lastInputAt.current, beatS.current)) {
        try {
          beatS.current = (await sendHeartbeat(workspaceId)).next_beat_s
        } catch {
          // Best-effort telemetry: a missed ping only undercounts a minute,
          // and must never surface to the user.
        }
      }
      if (!stopped) timer = setTimeout(() => void beat(), beatS.current * 1000)
    }
    // Ping on arrival and on every workspace switch, so the visit counts.
    lastInputAt.current = Date.now()
    void beat()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [enabled, workspaceId])
}
