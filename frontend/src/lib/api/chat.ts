import { apiFetch } from "./http"
import type { RunDto } from "./runs"

export interface ChatMessageDto {
  id: string
  role: "user" | "assistant"
  content: string
  created_at: string
}

export interface ChatThread {
  messages: ChatMessageDto[]
  /** The reply in progress, or the last reply if it failed. */
  reply_run: RunDto | null
}

export function getChat(workspaceId: string): Promise<ChatThread> {
  return apiFetch<ChatThread>(`/api/v1/workspaces/${workspaceId}/chat`)
}

export function sendChat(
  workspaceId: string,
  message: string,
): Promise<{ message: ChatMessageDto; reply_run: RunDto }> {
  return apiFetch(`/api/v1/workspaces/${workspaceId}/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  })
}
