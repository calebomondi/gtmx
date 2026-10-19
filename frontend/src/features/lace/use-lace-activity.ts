import { useCallback, useEffect, useRef, useState } from "react"

import { listLaceActivity, markLaceActivityRead, type ActivityDto } from "@/lib/api"

// How often the Feed looks for new activity.
const POLL_MS = 30_000
// Items per page: the backend's default page size.
const PAGE = 30

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export interface LaceActivity {
  items: ActivityDto[]
  loading: boolean
  error: string | null
  /** Items the founder has not seen, for the Feed button's badge. */
  unread: number
  /** Unseen when the Feed was opened during this visit to the Lace: shown with a dot. */
  isNew: (item: ActivityDto) => boolean
  /** More, older items may exist. */
  hasMore: boolean
  loadMore: () => Promise<void>
}

/** A Lace's activity, kept fresh. While `viewing` (the Feed is open) every
 * item is marked read on the server, yet the ones that were new keep their
 * dot until the founder leaves the Lace. */
export function useLaceActivity(laceId: string, viewing: boolean): LaceActivity {
  const [items, setItems] = useState<ActivityDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)
  // Ids that were unread when the founder opened the Feed.
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set())
  const latest = useRef<ActivityDto[]>([])

  const refresh = useCallback(async () => {
    const page = await listLaceActivity(laceId)
    if (latest.current.length === 0) setHasMore(page.length >= PAGE)
    // Keep older pages the founder loaded; replace the newest page.
    const known = new Set(page.map((a) => a.id))
    const older = latest.current.filter((a) => !known.has(a.id) && a.created_at < (page.at(-1)?.created_at ?? ""))
    latest.current = [...page, ...older]
    setItems(latest.current)
    return page
  }, [laceId])

  useEffect(() => {
    let cancelled = false
    const load = () => refresh()
      .then(() => !cancelled && setError(null))
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    void load()
    const timer = setInterval(load, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [refresh])

  // Opening the Feed (or new items arriving while it is open) marks them read.
  const unreadIds = items.filter((a) => a.read_at === null).map((a) => a.id).join(",")
  useEffect(() => {
    if (!viewing || !unreadIds) return
    const ids = unreadIds.split(",")
    markLaceActivityRead(laceId)
      .then(() => {
        const now = new Date().toISOString()
        latest.current = latest.current.map((a) => (a.read_at === null ? { ...a, read_at: now } : a))
        setItems(latest.current)
        setFresh((prev) => new Set([...prev, ...ids]))
      })
      .catch(() => undefined) // still unread: marked on the next look
  }, [viewing, unreadIds, laceId])

  const loadMore = useCallback(async () => {
    const before = latest.current.at(-1)?.created_at
    try {
      const page = await listLaceActivity(laceId, before)
      setHasMore(page.length >= PAGE)
      latest.current = [...latest.current, ...page]
      setItems(latest.current)
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  const unread = viewing ? 0 : items.filter((a) => a.read_at === null).length
  const isNew = useCallback((item: ActivityDto) => fresh.has(item.id), [fresh])
  return { items, loading, error, unread, isNew, hasMore, loadMore }
}
