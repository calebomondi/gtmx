export interface DiscoveryRequest {
  product_name: string
  product_url: string
  target_geo?: string[]
}

export interface SnapshotFeature {
  name: string | null
  description: string | null
  differentiator: string | null
}

/** Agent-side offer snapshot (mirrors agents.states.OfferDataSnapshot). */
export interface OfferSnapshot {
  company_name: string | null
  offer_name: string | null
  offer_description: string | null
  website_url: string | null
  intent: string | null
  target_geo: string[]
  problem_solved: string | null
  features: SnapshotFeature[]
  service_uniqueness: SnapshotFeature[]
  how_it_works: string | null
}

export type DiscoveryInterruptType =
  | "offer_name_mismatch"
  | "url_unscrappable"
  | "offer_type_clarification"
  | "product_service_description_confirmation"

export interface DiscoveryInterruptFrame {
  type: "interrupt"
  session_id: string
  interrupt_type: DiscoveryInterruptType
  question: string | null
  offer_name: string | null
  product_candidates: string[]
  draft: string | null
  url: string | null
  lean: string | null
}

export interface DiscoveryWorkspaceCreatedFrame {
  type: "workspace_created"
  session_id: string
  workspace_id: string
}

/** Top-level agent nodes, in execution order (mirrors backend NODE_ORDER). */
export type AgentNode =
  | "discover_offer"
  | "create_specialists"
  | "understand_offer"
  | "understand_market"
  | "understand_competition"
  | "determine_icp"

export type PhaseStatus = "started" | "done"

export interface DiscoveryPhaseFrame {
  type: "phase"
  session_id: string
  node: AgentNode
  status: PhaseStatus
}

/** A specialist on the created team (mirrors agents.sub_agents.schema_states.Specialist). */
export interface SpecialistDto {
  domain: "product" | "service" | "market" | "competition" | "gtm"
  affiliation: string
  name: string
  role: string
  description: string
}

export interface MarketDataDto {
  buyer_type: string | null
  category: string | null
  target_audience: string | null
  target_geo: string[]
  market_fit: string | null
  market_fit_reasoning: string | null
}

export interface CompetitorDto {
  name: string
  description: string
  website?: string | null
  offering?: string | null
  positioning?: string | null
  comparison?: string | null
}

export interface CompetitionDataDto {
  competitors: CompetitorDto[]
  strengths: string[]
  weaknesses: string[]
  opportunities: string[]
  differentiators: string[]
}

export interface CompetitorLeadDto {
  competitor_name: string
  search_queries: string[]
  pain_angles: string[]
}

export interface IcpDto {
  product_name: string | null
  buyer_type: string | null
  industries: string[]
  company_sizes: string[]
  geo: string[]
  buyer_titles: string[]
  exclusions: string[]
  pain_signals: string[]
  intent_keywords: string[]
  competitor_leads: CompetitorLeadDto[]
}

export type DiscoveryPhaseDataFrame =
  | {
      type: "phase_data"
      session_id: string
      node: "create_specialists"
      specialists: SpecialistDto[]
    }
  | {
      type: "phase_data"
      session_id: string
      node: "understand_offer"
      offer_domain_fit_understanding: string
    }
  | {
      type: "phase_data"
      session_id: string
      node: "understand_market"
      market_data: MarketDataDto
      product_market_fit_understanding: string | null
    }
  | {
      type: "phase_data"
      session_id: string
      node: "understand_competition"
      competition_data: CompetitionDataDto
    }
  | {
      type: "phase_data"
      session_id: string
      node: "determine_icp"
      icp_data: IcpDto
    }

export interface DiscoveryCompleteFrame {
  type: "complete"
  session_id: string
  workspace_id: string | null
  confirmed: boolean
  offer_snapshot: OfferSnapshot | null
  user_replies: string[]
}

export interface DiscoveryErrorFrame {
  type: "error"
  message: string
}

export type DiscoveryFrame =
  | DiscoveryInterruptFrame
  | DiscoveryWorkspaceCreatedFrame
  | DiscoveryPhaseFrame
  | DiscoveryPhaseDataFrame
  | DiscoveryCompleteFrame
  | DiscoveryErrorFrame

const DISCOVERY_PATH = "/api/v1/discover"
const DEFAULT_TIMEOUT_MS = 15_000

export class DiscoveryConnectionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "DiscoveryConnectionError"
  }
}

export function discoverySocketUrl(): string {
  const origin = import.meta.env.VITE_API_ORIGIN?.trim()
  const base = origin ? new URL(origin) : new URL(window.location.origin)
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:"
  return new URL(DISCOVERY_PATH, base).toString()
}

export class DiscoveryClient implements AsyncIterable<DiscoveryFrame> {
  private readonly socket: WebSocket
  private readonly frames: DiscoveryFrame[] = []
  private readonly waiters: Array<(frame: DiscoveryFrame | null) => void> = []
  private connectionError: Error | null = null
  private ended = false

  private constructor(socket: WebSocket) {
    this.socket = socket
    socket.onmessage = (event) => {
      const frame = parseFrame(event.data)
      const waiter = this.waiters.shift()
      if (waiter) waiter(frame)
      else this.frames.push(frame)
    }
    socket.onerror = () => {
      this.connectionError = new DiscoveryConnectionError(
        "discovery connection failed",
      )
      this.settle()
    }
    socket.onclose = () => this.settle()
  }

  static connect(
    request: DiscoveryRequest,
    options: { timeoutMs?: number; url?: string; signal?: AbortSignal } = {},
  ): Promise<DiscoveryClient> {
    const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
    const url = options.url ?? discoverySocketUrl()

    return new Promise<DiscoveryClient>((resolve, reject) => {
      if (options.signal?.aborted) {
        reject(new DiscoveryConnectionError(`connect cancelled: ${url}`))
        return
      }

      const socket = new WebSocket(url)
      let settled = false
      let timer = 0

      // Single exit point: whichever way the connect ends, clear the timer and
      // drop the abort listener so neither outlives the attempt.
      const settle = (finish: () => void): void => {
        if (settled) return
        settled = true
        window.clearTimeout(timer)
        options.signal?.removeEventListener("abort", onAbort)
        finish()
      }

      // The caller gave up before the handshake finished. Close the half-open
      // socket now -- left alone it stays parked against the origin's socket
      // pool and every later attempt queues behind it.
      function onAbort(): void {
        socket.close()
        settle(() =>
          reject(new DiscoveryConnectionError(`connect cancelled: ${url}`)),
        )
      }

      options.signal?.addEventListener("abort", onAbort, { once: true })

      timer = window.setTimeout(() => {
        // readyState tells the two failure modes apart: CONNECTING means the
        // handshake never completed (origin socket pool exhausted, proxy stall),
        // OPEN means we connected but the server never answered. Without this
        // both surface as the browser's "closed before the connection is
        // established" warning, which says nothing about the cause.
        const phase =
          socket.readyState === WebSocket.CONNECTING
            ? "handshake never completed"
            : "connected, no response from server"
        socket.close()
        settle(() =>
          reject(
            new DiscoveryConnectionError(`connect timed out (${phase}): ${url}`),
          ),
        )
      }, timeoutMs)

      socket.onopen = () => {
        if (settled) {
          socket.close()
          return
        }
        const client = new DiscoveryClient(socket)
        client.send(JSON.stringify(request))
        settle(() => resolve(client))
      }

      socket.onerror = () => {
        settle(() =>
          reject(new DiscoveryConnectionError(`could not connect: ${url}`)),
        )
      }

      socket.onclose = (event) => {
        settle(() =>
          reject(
            new DiscoveryConnectionError(
              `connection closed before ready (code ${event.code})`,
            ),
          ),
        )
      }
    })
  }

  get isClosed(): boolean {
    return this.ended
  }

  send(value: string): void {
    this.socket.send(value)
  }

  close(): void {
    this.settle()
    if (
      this.socket.readyState === WebSocket.OPEN ||
      this.socket.readyState === WebSocket.CONNECTING
    ) {
      this.socket.close()
    }
  }

  async next(): Promise<IteratorResult<DiscoveryFrame>> {
    if (this.frames.length > 0) {
      return { value: this.frames.shift()!, done: false }
    }
    if (this.connectionError) {
      throw this.connectionError
    }
    if (this.ended) {
      return { done: true, value: undefined }
    }
    const frame = await new Promise<DiscoveryFrame | null>((resolve) =>
      this.waiters.push(resolve),
    )
    if (frame === null) {
      if (this.connectionError) throw this.connectionError
      return { done: true, value: undefined }
    }
    return { value: frame, done: false }
  }

  [Symbol.asyncIterator](): AsyncIterator<DiscoveryFrame> {
    return this
  }

  private settle(): void {
    if (this.ended) return
    this.ended = true
    for (const waiter of this.waiters.splice(0)) waiter(null)
  }
}

function parseFrame(data: unknown): DiscoveryFrame {
  if (typeof data !== "string") {
    throw new Error("unsupported discovery frame payload")
  }
  return JSON.parse(data) as DiscoveryFrame
}

// ---------------------------------------------------------------------------
// REST helpers
// ---------------------------------------------------------------------------

const API_BASE = import.meta.env.VITE_API_ORIGIN?.trim() ?? ""

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  })

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === "string") detail = body.detail
    } catch {
      // non-JSON error body — keep the status text
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export interface CurrentUser {
  id: string
  name: string
  email: string
  avatar_url: string | null
  joined: string
  last_activity: string
}

export interface WorkspaceSummary {
  id: string
  user_id: string
  name: string | null
  pinned: boolean
  product_name: string | null
  project_id: string | null
  archived: boolean
  archived_at: string | null
  date_created: string
  last_activity: string
}

export interface ProjectDto {
  id: string
  user_id: string
  name: string
  name_key: string
  priority: boolean
  position: number
  archived: boolean
  archived_at: string | null
  date_created: string
  last_activity: string
  workspace_count: number
  archived_workspace_count: number
}

export interface ProjectDetailDto extends ProjectDto {
  workspaces: WorkspaceSummary[]
}

export function workspaceDisplayName(workspace: WorkspaceSummary): string {
  return workspace.name?.trim() || workspace.product_name?.trim() || "Untitled workspace"
}

let currentUserPromise: Promise<CurrentUser> | null = null

export function getCurrentUser(): Promise<CurrentUser> {
  currentUserPromise ??= apiFetch<CurrentUser>("/api/v1/users/me")
  return currentUserPromise
}

export function listWorkspaces(
  userId: string,
  archived = false,
): Promise<WorkspaceSummary[]> {
  return apiFetch<WorkspaceSummary[]>(
    `/api/v1/workspaces/user/${userId}${archived ? "?archived=true" : ""}`,
  )
}

export interface ProductFeatureDto {
  id: string
  name: string
  description: string | null
  differentiator: string | null
}

export interface ProductProfileDto {
  id: string
  workspace_id: string
  product_name: string | null
  product_url: string | null
  product_description: string | null
  intent: string | null
  problem_solved: string | null
  how_it_works: string | null
  target_geo: string[]
  confirmed: boolean
  features: ProductFeatureDto[]
}

/** Full workspace (includes archived ones); `product_profile` is eager-loaded. */
export interface WorkspaceDetail extends WorkspaceSummary {
  product_profile: ProductProfileDto | null
}

export function getWorkspace(workspaceId: string): Promise<WorkspaceDetail> {
  return apiFetch<WorkspaceDetail>(`/api/v1/workspaces/${workspaceId}`)
}

export function updateWorkspace(
  workspaceId: string,
  body: { name?: string; pinned?: boolean; project_id?: string | null },
): Promise<WorkspaceSummary> {
  return apiFetch<WorkspaceSummary>(`/api/v1/workspaces/${workspaceId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

export function deleteWorkspace(workspaceId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/workspaces/${workspaceId}`, {
    method: "DELETE",
  })
}

export function archiveWorkspace(workspaceId: string): Promise<WorkspaceSummary> {
  return apiFetch<WorkspaceSummary>(`/api/v1/workspaces/${workspaceId}/archive`, {
    method: "POST",
  })
}

export function restoreWorkspace(workspaceId: string): Promise<WorkspaceSummary> {
  return apiFetch<WorkspaceSummary>(`/api/v1/workspaces/${workspaceId}/restore`, {
    method: "POST",
  })
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export function listProjects(
  userId: string,
  archived = false,
): Promise<ProjectDto[]> {
  return apiFetch<ProjectDto[]>(
    `/api/v1/projects/user/${userId}${archived ? "?archived=true" : ""}`,
  )
}

export function createProject(userId: string, name: string): Promise<ProjectDto> {
  return apiFetch<ProjectDto>(`/api/v1/projects/user/${userId}`, {
    method: "POST",
    body: JSON.stringify({ name }),
  })
}

export function getProject(projectId: string): Promise<ProjectDetailDto> {
  return apiFetch<ProjectDetailDto>(`/api/v1/projects/${projectId}`)
}

export function renameProject(projectId: string, name: string): Promise<ProjectDto> {
  return apiFetch<ProjectDto>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  })
}

/** Persist the two-bucket drag order (`priority` / `other` = project ids). */
export function reorderProjects(
  userId: string,
  priority: string[],
  other: string[],
): Promise<void> {
  return apiFetch<void>(`/api/v1/projects/user/${userId}/order`, {
    method: "PUT",
    body: JSON.stringify({ priority, other }),
  })
}

export function archiveProject(projectId: string): Promise<ProjectDetailDto> {
  return apiFetch<ProjectDetailDto>(`/api/v1/projects/${projectId}/archive`, {
    method: "POST",
  })
}

export function restoreProject(projectId: string): Promise<ProjectDetailDto> {
  return apiFetch<ProjectDetailDto>(`/api/v1/projects/${projectId}/restore`, {
    method: "POST",
  })
}

export function deleteProject(projectId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/projects/${projectId}`, {
    method: "DELETE",
  })
}

/** Final discovery-run results persisted server-side when the run completes. */
export interface WorkspaceInsights {
  offer_snapshot: OfferSnapshot | null
  confirmed: boolean
  domain_understanding: string | null
  market_fit_understanding: string | null
  market_data: MarketDataDto | null
  competition_data: CompetitionDataDto | null
  icp: IcpDto | null
  specialists: SpecialistDto[] | null
  completed_at: string | null
}

export function getWorkspaceInsights(
  workspaceId: string,
): Promise<WorkspaceInsights | null> {
  return apiFetch<{ insights: WorkspaceInsights | null }>(
    `/api/v1/workspaces/${workspaceId}/insights`,
  ).then((body) => body.insights)
}
