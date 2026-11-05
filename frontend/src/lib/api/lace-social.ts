import { apiFetch } from "./http"

/** Where a Lace listens and reads the founder's posts. */
export type SocialPlatform = "x" | "instagram" | "facebook" | "tiktok" | "linkedin"
/** What something said is, as the Lace sorted it. */
export type HeardKind = "lead" | "question" | "feedback" | "praise" | "noise"
/** Where the founder is with it. */
export type HeardStatus = "new" | "done" | "dismissed"

/** One of the founder's posts, with how it did when last read. */
export interface SocialPostDto {
  id: string
  platform: SocialPlatform
  url: string
  text: string
  posted_at: string | null
  views: number | null
  likes: number | null
  comments: number | null
  shares: number | null
  read_at: string
}

/** A comment or mention the Lace's listen kept, sorted. */
export interface SocialItemDto {
  id: string
  platform: SocialPlatform
  author: string | null
  text: string
  url: string | null
  said_at: string | null
  verdict: HeardKind
  note: string
  status: HeardStatus
  heard_at: string
}

export function listSocialPosts(laceId: string): Promise<SocialPostDto[]> {
  return apiFetch<SocialPostDto[]>(`/api/v1/laces/${laceId}/social/posts?limit=100`)
}

export function listSocialHeard(laceId: string): Promise<SocialItemDto[]> {
  return apiFetch<SocialItemDto[]>(`/api/v1/laces/${laceId}/social/heard?limit=100`)
}

export function setSocialItemStatus(laceId: string, itemId: string, status: HeardStatus): Promise<SocialItemDto> {
  return apiFetch(`/api/v1/laces/${laceId}/social/heard/${itemId}`, { method: "PATCH", body: JSON.stringify({ status }) })
}
