import { useCallback, useEffect, useRef, useState } from "react"

// How often a feed looks for new activity.
const POLL_MS = 30_000
// Items per page: the backend's default page size.
const PAGE = 30

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export interface ActivityPages<T> {
  items: T[]
  loading: boolean
  error: string | null
  /** More, older items may exist. */
  hasMore: boolean
  loadMore: () => Promise<void>
  /** Change the loaded items in place, e.g. to stamp them read. */
  patch: (change: (item: T) => T) => void
}

/** A newest-first activity feed, paged back by created_at and polled for new
 * items. `fetchPage(before?)` must be stable (wrap it in useCallback). */
export function useActivityPages<T extends { id: string; created_at: string }>(
  fetchPage: (before?: string) => Promise<T[]>,
): ActivityPages<T> {
  const [items, setItems] = useState<T[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)
  const latest = useRef<T[]>([])

  const show = useCallback((next: T[]) => {
    latest.current = next
    setItems(next)
  }, [])

  useEffect(() => {
    let cancelled = false
    const load = () => fetchPage()
      .then((page) => {
        if (cancelled) return
        if (latest.current.length === 0) setHasMore(page.length >= PAGE)
        // Keep older pages the founder loaded; replace the newest page.
        const known = new Set(page.map((a) => a.id))
        const oldest = page.at(-1)?.created_at ?? ""
        show([...page, ...latest.current.filter((a) => !known.has(a.id) && a.created_at < oldest)])
        setError(null)
      })
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    void load()
    const timer = setInterval(load, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [fetchPage, show])

  const loadMore = useCallback(async () => {
    try {
      const page = await fetchPage(latest.current.at(-1)?.created_at)
      setHasMore(page.length >= PAGE)
      show([...latest.current, ...page])
    } catch (err) {
      setError(message(err))
    }
  }, [fetchPage, show])

  const patch = useCallback((change: (item: T) => T) => show(latest.current.map(change)), [show])

  return { items, loading, error, hasMore, loadMore, patch }
}
