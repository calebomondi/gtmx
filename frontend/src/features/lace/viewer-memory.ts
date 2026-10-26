import { useCallback, useState } from "react"

import type { ChatThread } from "@/lib/api"

/** What this browser remembers for the founder (what they opened, what they
 * have seen), a convenience only: storage can be blocked or cleared, and the
 * app then simply treats everything as not yet seen. */
function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Blocked or full: remembered for this visit only.
  }
}

/** Which chat with the Lace the founder last had open: the team's or their
 * own private one. */
export function useChatThread(scope: string): [ChatThread, (thread: ChatThread) => void] {
  const key = `lace.chat.${scope}`
  const [thread, setThread] = useState<ChatThread>(() => read<ChatThread>(key, "team") === "mine" ? "mine" : "team")
  const choose = useCallback((next: ChatThread) => {
    write(key, next)
    setThread(next)
  }, [key])
  return [thread, choose]
}

// Opened activity items kept per Lace; the oldest are forgotten past this.
const OPENED_KEPT = 300

/** Activity items the founder has followed, by id. */
export function useOpenedItems(scope: string): [ReadonlySet<string>, (id: string) => void] {
  const key = `lace.opened.${scope}`
  const [opened, setOpened] = useState(() => new Set(read<string[]>(key, [])))
  const mark = useCallback((id: string) => {
    setOpened((prev) => {
      if (prev.has(id)) return prev
      const next = new Set([...prev, id].slice(-OPENED_KEPT))
      write(key, [...next])
      return next
    })
  }, [key])
  return [opened, mark]
}

/** When the founder last looked at each kind of find, by kind. The first
 * visit counts as having seen everything, so only later finds glow. */
export function useSeenAt<K extends string>(scope: string): [(kind: K) => number, (kind: K) => void] {
  const key = `lace.seen.${scope}`
  const [seen, setSeen] = useState<Record<string, number>>(() => {
    const stored = read<Record<string, number> | null>(key, null)
    if (stored) return stored
    const first = { "*": Date.now() }
    write(key, first)
    return first
  })
  const seenAt = useCallback((kind: K) => seen[kind] ?? seen["*"] ?? 0, [seen])
  const markSeen = useCallback((kind: K) => {
    setSeen((prev) => {
      const next = { ...prev, [kind]: Date.now() }
      write(key, next)
      return next
    })
  }, [key])
  return [seenAt, markSeen]
}
