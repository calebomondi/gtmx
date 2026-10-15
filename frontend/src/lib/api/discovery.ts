import { getAccessToken } from "@/lib/supabase"

export interface DiscoveryRequest {
  product_name: string
  product_url: string
  target_geo?: string[]
  /** Asserted by the user on the intake form. The agent no longer classifies it. */
  offer_type?: 'product' | 'service'
  offer_description?: string
  /** Which intake path the backend should run: scrape the URL, or work from the description. */
  source?: 'website' | 'manual'
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
  | "offer_details_followup"

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

export interface MarketPricingDto {
  tier: string
  monthly_sub?: string | null
  yearly_sub?: string | null
  features: string[]
}

export interface MarketDataDto {
  buyer_type: string | null
  category: string | null
  target_audience: string | null
  target_geo: string[]
  market_fit: string | null
  market_fit_reasoning: string | null
  pricing?: MarketPricingDto[]
  pricing_source?: "site" | "market_suggestion" | null
  category_conventions?: string | null
  market_demand?: string | null
  willingness_to_pay?: string | null
  distribution_channels?: string[]
  adoption_barriers?: string[]
  growth_outlook?: "growing" | "stable" | "declining" | "unclear" | null
}

/** One archetype in the ideal competitor profile.
 *
 * A CONSTRUCT, not a company: "Regional incumbent undercutting on price" makes
 * no claim that any firm exists. That is why it has no name and no website, and
 * why the profile is allowed to be aggressive. It is the exact inverse of
 * `CompetitorDto`, which is a set of sourced claims about a verified real firm. */
export interface CompetitorArchetypeDto {
  label: string
  archetype_description: string
  geography_scope: "local" | "regional" | "global" | "any"
  business_model?: string | null
  typical_offering?: string | null
  pricing_model?: string | null
  customer_profile?: string | null
  likely_advantages: string[]
  likely_weaknesses: string[]
  where_to_find_them: string[]
  confidence: "high" | "medium" | "low"
}

/** The competition stage's primary output: what a perfect competitor looks
 * like here, deliberately not geo-bounded, naming nobody. */
export interface IdealCompetitorProfileDto {
  category_definition: string
  boundary_of_category: string[]
  archetypes: CompetitorArchetypeDto[]
  global_entry_signals: string[]
  local_defence_signals: string[]
  substitution_risks: string[]
  price_anchor_range?: string | null
  channels: string[]
  confidence: "high" | "medium" | "low"
}

/** The offer-vs-standard SWOD. It used to carry a `competitors: CompetitorDto[]`
 * name list; that moved to the archetype profile and, for real verified rivals,
 * to the standalone competitor agent. */
export interface CompetitionDataDto {
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

export interface BuyerPersonaDto {
  name: string
  who: string
  where_they_congregate: string[]
  intent_signals: string[]
}

export interface TargetChannelDto {
  channel_type: string
  name: string
  audience_fit: string
  first_angle: string
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
  buyer_personas?: BuyerPersonaDto[]
  target_channels?: TargetChannelDto[]
  event_focus?: string | null
  messaging_angles?: string[]
  beachhead?: string | null
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
      ideal_competitor_profile: IdealCompetitorProfileDto | null
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

/** Sent first on every connection: the run this socket is attached to. */
export interface DiscoveryRunFrame {
  type: "run"
  run_id: string
}

/** Someone (this tab, another tab or device) answered the pending question. */
export interface DiscoveryAnsweredFrame {
  type: "answered"
  answer: string
}

export interface DiscoveryCancelledFrame {
  type: "cancelled"
  message: string
}

/** A rejected client action (e.g. answering when nothing is asked). */
export interface DiscoveryNoticeFrame {
  type: "notice"
  message: string
}

/** Persisted run frames carry their run and a monotonic cursor for resume. */
export interface RunFrameMeta {
  run_id?: string
  event_id?: number
}

export type DiscoveryFrame = RunFrameMeta & (
  | DiscoveryRunFrame
  | DiscoveryInterruptFrame
  | DiscoveryWorkspaceCreatedFrame
  | DiscoveryPhaseFrame
  | DiscoveryPhaseDataFrame
  | DiscoveryAnsweredFrame
  | DiscoveryCompleteFrame
  | DiscoveryErrorFrame
  | DiscoveryCancelledFrame
  | DiscoveryNoticeFrame
)

/** Reattach to an existing run, replaying every frame after `after`. */
export interface DiscoveryResume {
  resume: string
  after: number
}

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

  static async connect(
    opening: DiscoveryRequest | DiscoveryResume,
    options: { timeoutMs?: number; url?: string; signal?: AbortSignal } = {},
  ): Promise<DiscoveryClient> {
    const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
    const baseUrl = options.url ?? discoverySocketUrl()
    const token = await getAccessToken()
    const url = token
      ? `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`
      : baseUrl

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
        client.send(JSON.stringify(opening))
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

  get isOpen(): boolean {
    return !this.ended && this.socket.readyState === WebSocket.OPEN
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
