import { apiFetch } from "./http"

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------

export interface AccountRecord {
  id: string
  workspace_id: string
  run_id: string | null
  name: string
  account_type: string
  website: string | null
  domain: string | null
  platform: string | null
  venue: string | null
  event_date: string | null
  member_size: string | null
  summary: string | null
  industry: string | null
  size: string | null
  geo: string | null
  tech_stack: string[]
  recent_news: string[]
  key_contacts: Array<Record<string, unknown>>
  pain_signals: string[]
  hiring_signals: string[]
  sources: Array<Record<string, unknown>>
  source_queries: string[]
  score: number | null
  score_breakdown: string | null
  why_selected: string[]
  why_reach_out: string[]
  trigger_event: Record<string, unknown> | null
  selected: boolean
  created_at: string
}

export interface AccountList {
  accounts: AccountRecord[]
  total: number
}

export interface AccountRun {
  id: string
  workspace_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  error: string | null
  candidates_seen: number
  found: number
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface AccountRunStart {
  run: AccountRun
  already_tracked: number
}

export function startAccountRun(workspaceId: string): Promise<AccountRunStart> {
  return apiFetch<AccountRunStart>(
    `/api/v1/workspaces/${workspaceId}/accounts/runs`,
    { method: 'POST' },
  )
}

export function getAccountRun(workspaceId: string, runId: string): Promise<AccountRun> {
  return apiFetch<AccountRun>(`/api/v1/workspaces/${workspaceId}/accounts/runs/${runId}`)
}

export function listAccountRuns(workspaceId: string, limit = 20): Promise<AccountRun[]> {
  return apiFetch<AccountRun[]>(
    `/api/v1/workspaces/${workspaceId}/accounts/runs?limit=${limit}`,
  )
}

export function listAccounts(workspaceId: string): Promise<AccountList> {
  return apiFetch<AccountList>(`/api/v1/workspaces/${workspaceId}/accounts`)
}

export function updateAccount(
  workspaceId: string,
  accountId: string,
  patch: { selected?: boolean },
): Promise<AccountRecord> {
  return apiFetch<AccountRecord>(
    `/api/v1/workspaces/${workspaceId}/accounts/${accountId}`,
    { method: 'PATCH', body: JSON.stringify(patch) },
  )
}
