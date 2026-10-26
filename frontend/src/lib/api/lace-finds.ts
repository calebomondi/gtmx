import { apiFetch } from "./http"

/** What a private chat can find. Mirrors agents' SavedKind. */
export type FindKind = "competitor" | "account" | "opportunity"

/** A member's private find, or one pushed to the team. Mirrors FindResponse. */
export interface FindDto {
  kind: FindKind
  id: string
  name: string
  /** Its website, or an opportunity's organiser. */
  detail: string | null
  status: string
  /** Pushed to the team, waiting for review. */
  proposed_at: string | null
  /** Why it was sent back, when it was. */
  review_note: string | null
  /** Who found it (in the team's review list). */
  owner?: { id: string; name: string | null; avatar_url: string | null } | null
  /** Whether the viewer may approve it or send it back. */
  can_review?: boolean | null
}

/** Your private chat's finds that you haven't dismissed. */
export function listMyFinds(laceId: string): Promise<FindDto[]> {
  return apiFetch<FindDto[]>(`/api/v1/laces/${laceId}/my-finds`)
}

/** Put finds up for the team's review; how many went up. */
export function pushFinds(laceId: string, finds: Pick<FindDto, "kind" | "id">[]): Promise<{ pushed: number }> {
  return apiFetch(`/api/v1/laces/${laceId}/my-finds/push`, {
    method: "POST", body: JSON.stringify({ items: finds.map(({ kind, id }) => ({ kind, id })) }),
  })
}

/** Finds pushed to the team, waiting for someone to approve them. */
export function listFindReviews(laceId: string): Promise<FindDto[]> {
  return apiFetch<FindDto[]>(`/api/v1/laces/${laceId}/reviews`)
}

export function approveFind(laceId: string, find: FindDto): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/reviews/${find.kind}/${find.id}/approve`, { method: "POST" })
}

export function sendBackFind(laceId: string, find: FindDto, note: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/reviews/${find.kind}/${find.id}/send-back`, {
    method: "POST", body: JSON.stringify({ note: note.trim() || null }),
  })
}
