import { apiFetch } from "./http"
import type { RunDto } from "./runs"

export interface OutreachMessageDto {
  id: string
  account_id: string | null
  channel: "email" | "linkedin"
  recipient_name: string | null
  recipient_company: string
  recipient_address: string | null
  subject: string | null
  body: string
  status: "draft" | "sending" | "sent" | "failed"
  error: string | null
  sent_at: string | null
  created_at: string
  updated_at: string
}

export interface OutreachList {
  messages: OutreachMessageDto[]
  drafting_run: RunDto | null
}

export type OutreachChanges = Partial<Pick<OutreachMessageDto, "subject" | "body" | "recipient_address" | "recipient_name">>

const base = (workspaceId: string) => `/api/v1/workspaces/${workspaceId}/outreach`

export function listOutreach(workspaceId: string): Promise<OutreachList> {
  return apiFetch(base(workspaceId))
}

/** Ask the agent to draft one message per account; poll listOutreach. */
export function draftOutreach(workspaceId: string, accountIds: string[], channel: "email" | "linkedin"): Promise<RunDto> {
  return apiFetch(`${base(workspaceId)}/drafts`, {
    method: "POST",
    body: JSON.stringify({ account_ids: accountIds, channel }),
  })
}

export function updateOutreachMessage(workspaceId: string, messageId: string, changes: OutreachChanges): Promise<OutreachMessageDto> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}`, { method: "PATCH", body: JSON.stringify(changes) })
}

/** Send one approved email through the user's connected Gmail. */
export function sendOutreachMessage(workspaceId: string, messageId: string): Promise<OutreachMessageDto> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}/send`, { method: "POST" })
}

export function deleteOutreachMessage(workspaceId: string, messageId: string): Promise<void> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}`, { method: "DELETE" })
}
