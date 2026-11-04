import { apiFetch } from "./http"

/** What a standing instruction governs; "everything" holds in every chat and job. */
export type InstructionScope = "everything" | "competitors" | "leads" | "opportunities" | "outreach"

export const INSTRUCTION_SCOPES: InstructionScope[] = ["everything", "competitors", "leads", "opportunities", "outreach"]

/** Longest instruction the backend keeps. */
export const INSTRUCTION_CHARS = 300

/** How the team wants its Lace to work, kept from the chat or added in settings. */
export interface LaceInstructionDto {
  id: string
  text: string
  applies_to: InstructionScope
  created_by: string | null
  created_at: string
  updated_at: string | null
}

export function listLaceInstructions(laceId: string): Promise<LaceInstructionDto[]> {
  return apiFetch<LaceInstructionDto[]>(`/api/v1/laces/${laceId}/instructions`)
}

export function addLaceInstruction(laceId: string, text: string, appliesTo: InstructionScope): Promise<LaceInstructionDto> {
  return apiFetch(`/api/v1/laces/${laceId}/instructions`, {
    method: "POST", body: JSON.stringify({ text, applies_to: appliesTo }),
  })
}

export function editLaceInstruction(laceId: string, id: string, text: string,
                                    appliesTo: InstructionScope): Promise<LaceInstructionDto> {
  return apiFetch(`/api/v1/laces/${laceId}/instructions/${id}`, {
    method: "PATCH", body: JSON.stringify({ text, applies_to: appliesTo }),
  })
}

export function deleteLaceInstruction(laceId: string, id: string): Promise<void> {
  return apiFetch(`/api/v1/laces/${laceId}/instructions/${id}`, { method: "DELETE" })
}
