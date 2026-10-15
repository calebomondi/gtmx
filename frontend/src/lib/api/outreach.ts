import { apiFetch } from "./http"
import type { RunDto } from "./runs"

export interface OutreachMessageDto {
  id: string
  account_id: string | null
  channel: "email" | "linkedin"
  /** inbound = a reply or bounce synced from the user's Gmail. */
  direction: "outbound" | "inbound"
  thread_id: string | null
  read_at: string | null
  /** How the GTM specialist read a reply (inbound only). */
  intent: string | null
  /** A reply draft's proposed meeting; event_url once added to Calendar. */
  meeting: { start: string; end: string; timezone: string; title: string; attendee: string | null; event_url?: string } | null
  recipient_name: string | null
  recipient_company: string
  recipient_address: string | null
  subject: string | null
  body: string
  status: "draft" | "sending" | "sent" | "failed" | "bounced" | "received"
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

/** Ask the GTM specialist to draft one message per account; poll listOutreach.
 *  `recipient` picks the contact when drafting for a single account. */
export function draftOutreach(
  workspaceId: string,
  accountIds: string[],
  channel: "email" | "linkedin",
  recipient?: { name?: string; address?: string },
): Promise<RunDto> {
  return apiFetch(`${base(workspaceId)}/drafts`, {
    method: "POST",
    body: JSON.stringify({ account_ids: accountIds, channel, recipient: recipient ?? null }),
  })
}

export function updateOutreachMessage(workspaceId: string, messageId: string, changes: OutreachChanges): Promise<OutreachMessageDto> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}`, { method: "PATCH", body: JSON.stringify(changes) })
}

/** Send one approved email through the user's connected Gmail. */
export function sendOutreachMessage(workspaceId: string, messageId: string): Promise<OutreachMessageDto> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}/send`, { method: "POST" })
}

/** Check the user's Gmail for replies and bounces now. */
export function syncOutreach(workspaceId: string): Promise<{ replies: number; bounced: number }> {
  return apiFetch(`${base(workspaceId)}/sync`, { method: "POST" })
}

export function markOutreachRead(workspaceId: string, messageId: string): Promise<OutreachMessageDto> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}/read`, { method: "POST" })
}

/** Ask the GTM specialist to draft an answer to a received reply. */
export function draftOutreachReply(workspaceId: string, messageId: string): Promise<RunDto> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}/reply-draft`, { method: "POST" })
}

/** Add a reply draft's proposed meeting to the user's Google Calendar. */
export function addOutreachMeeting(workspaceId: string, messageId: string): Promise<OutreachMessageDto> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}/meeting`, { method: "POST" })
}

export function deleteOutreachMessage(workspaceId: string, messageId: string): Promise<void> {
  return apiFetch(`${base(workspaceId)}/messages/${messageId}`, { method: "DELETE" })
}
