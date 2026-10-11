import { useEffect, useMemo, useState } from "react"

import { ApiError, SEARCH_MIN_LENGTH, searchAll, type SearchHitDto, type SearchKind } from "@/lib/api"

const DEBOUNCE_MS = 200

interface Result {
  term: string
  hits: SearchHitDto[]
  error: string | null
}

export interface SearchState {
  /** Too short to search: show the default (recent) view instead. */
  idle: boolean
  loading: boolean
  error: string | null
  groups: [SearchKind, SearchHitDto[]][]
}

/** Debounced server search; a newer query aborts the one in flight. */
export function useSearch(query: string): SearchState {
  const term = query.trim()
  const [result, setResult] = useState<Result>({ term: "", hits: [], error: null })

  useEffect(() => {
    if (term.length < SEARCH_MIN_LENGTH) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchAll(term, controller.signal)
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
    const byKind = new Map<SearchKind, SearchHitDto[]>()
    for (const hit of result.hits) byKind.set(hit.kind, [...(byKind.get(hit.kind) ?? []), hit])
    return [...byKind.entries()]
  }, [result.hits])

  const idle = term.length < SEARCH_MIN_LENGTH
  return {
    idle,
    loading: !idle && result.term !== term,
    error: idle ? null : result.error,
    // While the next query loads, keep showing the last results rather than flashing empty.
    groups: idle ? [] : groups,
  }
}
