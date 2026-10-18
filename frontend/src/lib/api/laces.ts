import { apiFetch } from "./http"

export type LaceStatus = "onboarding" | "active" | "archived"

export type FactTopic =
  | "company"
  | "offer"
  | "pricing"
  | "customers"
  | "market"
  | "competition"
  | "icp"
  | "positioning"

export interface LaceDto {
  id: string
  name: string
  website: string
  startup_name: string | null
  status: LaceStatus
  created_at: string
}

export interface FactDto {
  id: string
  topic: FactTopic
  claim: string
  source_url: string | null
  confidence: "high" | "medium" | "low"
  origin: "crawl" | "research" | "user" | "monitor"
  recorded_at: string
}

export interface LaceMessageDto {
  role: "founder" | "lace"
  content: string
}

export function createLace(name: string, website: string): Promise<{ lace: LaceDto; run_id: string }> {
  return apiFetch("/api/v1/laces", { method: "POST", body: JSON.stringify({ name, website }) })
}

export function listLaces(): Promise<LaceDto[]> {
  return apiFetch<LaceDto[]>("/api/v1/laces")
}

export function getLace(laceId: string): Promise<LaceDto> {
  return apiFetch<LaceDto>(`/api/v1/laces/${laceId}`)
}

export function listLaceFacts(laceId: string): Promise<FactDto[]> {
  return apiFetch<FactDto[]>(`/api/v1/laces/${laceId}/facts`)
}

export function listLaceMessages(laceId: string): Promise<LaceMessageDto[]> {
  return apiFetch<LaceMessageDto[]>(`/api/v1/laces/${laceId}/messages`)
}

/** Starts a turn; follow its run for the reply. */
export function sendLaceMessage(laceId: string, text: string): Promise<{ run_id: string }> {
  return apiFetch(`/api/v1/laces/${laceId}/messages`, { method: "POST", body: JSON.stringify({ text }) })
}
