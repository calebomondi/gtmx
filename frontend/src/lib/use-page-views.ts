import { useEffect, useRef } from "react"
import { matchPath, useLocation } from "react-router-dom"

import { track } from "@/lib/events"

// The app's pages by route, named for the event log; a Lace's tab and its
// sub-tab (the hash) make up the rest of the name.
const PAGES: [pattern: string, page: string][] = [
  ["/feed", "home_feed"],
  ["/lace", "laces"],
  ["/new", "new_lace"],
  ["/accounts", "accounts"],
  ["/lace/:lace_id/setup", "lace_setup"],
  ["/lace/:lace_id/:tab", "lace"],
  ["/lace/:lace_id", "lace"],
]

function pageView(pathname: string, hash: string): { detail: string; laceId: string | null } {
  for (const [pattern, page] of PAGES) {
    const match = matchPath(pattern, pathname)
    if (!match) continue
    const name = page === "lace" ? `lace_${match.params.tab ?? "feed"}` : page
    const section = hash.replace(/^#/, "")
    return { detail: section ? `${name}#${section}` : name, laceId: match.params.lace_id ?? null }
  }
  return { detail: "other", laceId: null }
}

/** A page_viewed event each time the page (or a Lace's sub-tab) changes,
 * while `enabled` (signed in and let into the app). */
export function usePageViews(enabled: boolean) {
  const { pathname, hash } = useLocation()
  // React runs effects twice in development; one view is one event.
  const last = useRef<string | null>(null)
  useEffect(() => {
    const key = pathname + hash
    if (!enabled || last.current === key) return
    last.current = key
    track("page_viewed", pageView(pathname, hash))
  }, [enabled, pathname, hash])
}
