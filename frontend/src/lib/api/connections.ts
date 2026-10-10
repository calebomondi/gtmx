import { apiFetch } from "./http"

export interface ChannelDto {
  platform: string
  /** False until the app-level OAuth setup exists for this channel. */
  available: boolean
}

export interface ConnectionDto {
  id: string
  platform: string
  status: "live" | "pending" | "needs_attention"
  display_name: string | null
  created_at: string | null
  updated_at: string | null
}

export function listConnections(): Promise<{ channels: ChannelDto[]; connections: ConnectionDto[] }> {
  return apiFetch("/api/v1/connections")
}

/** A Composio Connect Link; the user comes back to /accounts?connected=<platform>. */
export function startConnection(platform: string): Promise<{ redirect_url: string }> {
  return apiFetch(`/api/v1/connections/${platform}`, { method: "POST" })
}

export function deleteConnection(connectionId: string): Promise<void> {
  return apiFetch(`/api/v1/connections/${connectionId}`, { method: "DELETE" })
}
