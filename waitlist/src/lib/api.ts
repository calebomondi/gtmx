/** The Thalace waitlist API. Types mirror backend/app/schemas/waitlist.py. */

export type Stage = 'idea' | 'pre_revenue' | 'revenue' | 'scaling'
export type SellsTo = 'b2b' | 'b2c' | 'both'

export interface WaitlistSource {
  utm_source?: string
  utm_medium?: string
  utm_campaign?: string
  referrer?: string
}

export interface WaitlistJoined {
  token: string
  pilot_spots_left: number
}

export interface WaitlistDetails {
  name?: string
  company?: string
  role?: string
  stage?: Stage
  sells_to?: SellsTo
  countries?: string[]
  wants_pilot?: boolean
  expectations?: string
  /** Their startup's website; a bare host is fine. */
  website?: string
}

export interface WaitlistSaved {
  wants_pilot: boolean
  pilot_spots_left: number
}

export interface PilotSpots {
  total: number
  taken: number
  left: number
  /** When the current cohort starts, as YYYY-MM-DD. */
  starts_on: string
}

export const EXPECTATIONS_MAX_CHARS = 500

// The backend's own address when it isn't on this site's origin (Render);
// empty when /api is proxied here (local dev, or nginx in front of both).
const API_ORIGIN = ((import.meta.env.VITE_API_ORIGIN as string | undefined) ?? '').trim().replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** What to tell the visitor when a call fails, in their terms. */
function messageFor(status: number, detail: unknown): string {
  if (status === 429) return 'Too many signups from this network right now. Please try again in an hour.'
  if (typeof detail === 'string' && status < 500) return detail
  if (status === 422) return 'Please check your email address and tick the consent box.'
  return "We couldn't reach Thalace just now. Please try again in a moment."
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_ORIGIN}/api/v1/waitlist${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, messageFor(0, null))
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, messageFor(response.status, body?.detail))
  }
  return (await response.json()) as T
}

export function joinWaitlist(email: string, source: WaitlistSource, nickname: string): Promise<WaitlistJoined> {
  return call('', { method: 'POST', body: JSON.stringify({ email, consent: true, source, nickname: nickname || null }) })
}

export function saveDetails(token: string, details: WaitlistDetails): Promise<WaitlistSaved> {
  return call(`/${encodeURIComponent(token)}`, { method: 'PATCH', body: JSON.stringify(details) })
}

export function getPilotSpots(): Promise<PilotSpots> {
  return call('/pilot')
}
