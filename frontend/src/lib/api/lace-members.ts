import { apiFetch } from "./http"

/** Who someone is to a Lace: its creator, those who manage it with them, the rest of the team. */
export type LaceRole = "owner" | "admin" | "member"

export interface LacePersonDto {
  user_id: string
  name: string | null
  email: string | null
  avatar_url: string | null
  role: LaceRole
  /** invited: not answered yet; requested: asked to join, waiting to be let in. */
  status: "invited" | "requested" | "active"
}

export interface LaceInviteDto {
  lace_id: string
  lace_name: string
  startup_name: string | null
  website: string
  role: LaceRole
  /** Who invited them: a name or an email. */
  invited_by: string | null
  invited_at: string
}

export function listLaceMembers(laceId: string): Promise<LacePersonDto[]> {
  return apiFetch(`/api/v1/laces/${laceId}/members`)
}

/** Invite someone who has signed up; only the owner invites admins. */
export function inviteLaceMember(laceId: string, email: string, role: "admin" | "member"): Promise<LacePersonDto> {
  return apiFetch(`/api/v1/laces/${laceId}/members`, { method: "POST", body: JSON.stringify({ email, role }) })
}

export function changeLaceRole(laceId: string, userId: string, role: "admin" | "member"): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/members/${userId}`, { method: "PATCH", body: JSON.stringify({ role }) })
}

/** Take someone off the Lace, withdraw their invite, or turn down their request. */
export function removeLaceMember(laceId: string, userId: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/members/${userId}`, { method: "DELETE" })
}

/** Let in someone who asked to join. */
export function approveLaceMember(laceId: string, userId: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/members/${userId}/approve`, { method: "POST" })
}

export function leaveLace(laceId: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/leave`, { method: "POST" })
}

export function listLaceInvites(): Promise<LaceInviteDto[]> {
  return apiFetch("/api/v1/laces/invites")
}

export function answerLaceInvite(laceId: string, answer: "accept" | "decline"): Promise<void> {
  return apiFetch(`/api/v1/laces/invites/${laceId}/${answer}`, { method: "POST" })
}

/** Whether the startup at this website already has a Lace (one per startup). */
export function checkLaceClaimed(website: string): Promise<{ domain: string; taken: boolean }> {
  return apiFetch(`/api/v1/laces/claimed?website=${encodeURIComponent(website)}`)
}

/** Ask the people on the Lace of the startup at this website to let you in. */
export function askToJoinLace(website: string): Promise<void> {
  return apiFetch("/api/v1/laces/requests", { method: "POST", body: JSON.stringify({ website }) })
}
