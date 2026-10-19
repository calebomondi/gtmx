import { useCallback, useEffect, useState } from "react"

import { listLaceActivity, markLaceActivityRead, type ActivityDto } from "@/lib/api"

import { useActivityPages, type ActivityPages } from "./use-activity-pages"

export interface LaceActivity extends ActivityPages<ActivityDto> {
  /** Items the founder has not seen, for the Feed button's badge. */
  unread: number
  /** Unseen when the Feed was opened during this visit to the Lace: shown with a dot. */
  isNew: (item: ActivityDto) => boolean
}

/** A Lace's activity, kept fresh. While `viewing` (the Feed is open) every
 * item is marked read on the server, yet the ones that were new keep their
 * dot until the founder leaves the Lace. */
export function useLaceActivity(laceId: string, viewing: boolean): LaceActivity {
  const fetchPage = useCallback((before?: string) => listLaceActivity(laceId, before), [laceId])
  const pages = useActivityPages(fetchPage)
  const { items, patch } = pages
  // Ids that were unread when the founder opened the Feed.
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set())

  // Opening the Feed (or new items arriving while it is open) marks them read.
  const unreadIds = items.filter((a) => a.read_at === null).map((a) => a.id).join(",")
  useEffect(() => {
    if (!viewing || !unreadIds) return
    const ids = unreadIds.split(",")
    markLaceActivityRead(laceId)
      .then(() => {
        const now = new Date().toISOString()
        patch((a) => (a.read_at === null ? { ...a, read_at: now } : a))
        setFresh((prev) => new Set([...prev, ...ids]))
      })
      .catch(() => undefined) // still unread: marked on the next look
  }, [viewing, unreadIds, laceId, patch])

  const unread = viewing ? 0 : items.filter((a) => a.read_at === null).length
  const isNew = useCallback((item: ActivityDto) => fresh.has(item.id), [fresh])
  return { ...pages, unread, isNew }
}
