import { apiFetch } from "./http"

export type SearchKind = "workspace" | "project" | "competitor" | "account" | "signal"

export interface SearchHitDto {
  kind: SearchKind
  id: string
  title: string
  subtitle: string | null
  workspace_id: string | null
  archived: boolean
  offer_type: "product" | "service" | null
}

interface SearchResponseDto {
  hits: SearchHitDto[]
}

/** Shorter than this the API matches nothing, so don't ask. */
export const SEARCH_MIN_LENGTH = 2

/** Everything the user owns whose name matches, grouped by kind. */
export async function searchAll(query: string, signal?: AbortSignal): Promise<SearchHitDto[]> {
  const params = new URLSearchParams({ q: query })
  const response = await apiFetch<SearchResponseDto>(`/api/v1/search?${params}`, { signal })
  return response.hits
}
