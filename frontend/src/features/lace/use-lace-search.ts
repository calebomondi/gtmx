import { useEffect, useMemo, useState } from "react"

import { ApiError, LACE_SEARCH_MIN_LENGTH, searchLaces, type LaceSearchHitDto, type LaceSearchKind } from "@/lib/api"

const DEBOUNCE_MS = 200

interface Result {
  term: string
  hits: LaceSearchHitDto[]
  error: string | null
}

export interface LaceSearchState {
  /** Too short to search: show the default view instead. */
  idle: boolean
  loading: boolean
  error: string | null
  groups: [LaceSearchKind, LaceSearchHitDto[]][]
}

/** Debounced search across the founder's Laces; a newer query aborts the one in flight. */
export function useLaceSearch(query: string): LaceSearchState {
  const term = query.trim()
  const [result, setResult] = useState<Result>({ term: "", hits: [], error: null })

  useEffect(() => {
    if (term.length < LACE_SEARCH_MIN_LENGTH) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchLaces(term, controller.signal)
        .then((hits) => setResult({ term, hits, error: null }))
        .catch((error: unknown) => {
          if (controller.signal.aborted) return
          const message = error instanceof ApiError ? error.message : "Search is unavailable right now."
          setResult({ term, hits: [], error: message })
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [term])

  const groups = useMemo(() => {
    const byKind = new Map<LaceSearchKind, LaceSearchHitDto[]>()
    for (const hit of result.hits) byKind.set(hit.kind, [...(byKind.get(hit.kind) ?? []), hit])
    return [...byKind.entries()]
  }, [result.hits])

  const idle = term.length < LACE_SEARCH_MIN_LENGTH
  return {
    idle,
    loading: !idle && result.term !== term,
    error: idle ? null : result.error,
    // While the next query loads, keep the last results rather than flashing empty.
    groups: idle ? [] : groups,
  }
}

/** Ctrl+K / ⌘K toggles search from anywhere in the app. */
export function useSearchShortcut(toggle: () => void) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        toggle()
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [toggle])
}
