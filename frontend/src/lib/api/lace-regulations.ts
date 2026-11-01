import { apiFetch } from "./http"

/** Where the startup is registered and operates, as ISO 3166 codes (KE, US-DE). */
export interface JurisdictionDto {
  registered_in: string | null
  operates_in: string[]
  /** When a founder confirmed it; laws are searched only after that. */
  jurisdiction_confirmed_at: string | null
}

export type RegulationKind = "law" | "regulation" | "bill" | "obligation"
export type BillStage =
  | "published" | "first_reading" | "committee" | "second_reading" | "whole_house" | "third_reading"
  | "assented" | "withdrawn" | "lapsed"
export type RegulationStatus = "suggested" | "tracked" | "dismissed"

export interface LaceRegulationDto {
  id: string
  kind: RegulationKind
  title: string
  authority: string | null
  jurisdiction: string
  url: string
  /** Bills only, once read from the bill tracker. */
  stage: BillStage | null
  stage_changed_at: string | null
  in_force_on: string | null
  next_date: string | null
  why_it_applies: string
  what_to_do: string
  status: RegulationStatus
  first_seen_at: string
  last_checked_at: string | null
}

export function getJurisdiction(laceId: string): Promise<JurisdictionDto> {
  return apiFetch(`/api/v1/laces/${laceId}/jurisdiction`)
}

/** Confirm where the startup is registered and operates. */
export function setJurisdiction(laceId: string, registeredIn: string | null, operatesIn: string[]): Promise<JurisdictionDto> {
  return apiFetch(`/api/v1/laces/${laceId}/jurisdiction`, {
    method: "PUT", body: JSON.stringify({ registered_in: registeredIn, operates_in: operatesIn }),
  })
}

export function listLaceRegulations(laceId: string, status: RegulationStatus = "tracked"): Promise<LaceRegulationDto[]> {
  return apiFetch(`/api/v1/laces/${laceId}/regulations?status=${status}`)
}

/** Track a regulation (the Lace watches it) or drop it (dismissed: not for us). */
export function setLaceRegulationStatus(laceId: string, regulationId: string,
                                        status: Exclude<RegulationStatus, "suggested">): Promise<LaceRegulationDto> {
  return apiFetch(`/api/v1/laces/${laceId}/regulations/${regulationId}`, {
    method: "PATCH", body: JSON.stringify({ status }),
  })
}
