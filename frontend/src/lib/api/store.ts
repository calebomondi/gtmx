import { apiFetch } from "./http"

/** setup: being configured, nothing on sale. live: selling. paused: the team
 * stopped new checkouts (the wallet's own freeze is `frozen_at`). */
export type StoreStatus = "setup" | "live" | "paused"
/** A private link emailed to the buyer, or a service the team delivers. */
export type OfferDelivery = "link" | "service"
export type OfferStatus = "draft" | "active" | "archived"
/** To another NEAR Intents account, or out to an address on a chain. */
export type PayeeRoute = "transfer" | "withdraw"

export interface StoreDto {
  id: string
  slug: string
  name: string
  tagline: string
  status: StoreStatus
  /** Whether its tab shows on the Lace's rail. */
  shown: boolean
  settlement_asset: string
  /** The most it may send out in a day, in USD, as a decimal string. */
  daily_budget_usd: string
  /** The NEAR account the owner's passkey controls, once the wallet exists. */
  owner_account_id: string | null
  /** Whether a passkey to sign with was added. */
  has_owner: boolean
  /** The Store's own NEAR Intents account, where sales land. */
  wallet_account_id: string | null
  frozen_at: string | null
  live_since: string | null
}

export interface StoreUpdate {
  name?: string
  tagline?: string
  slug?: string
  daily_budget_usd?: string
}

export interface OfferDto {
  id: string
  title: string
  description: string
  price_cents: number
  delivery: OfferDelivery
  delivery_url: string | null
  delivery_note: string
  status: OfferStatus
  /** Drafted by the Lace in chat; a person puts it on sale. */
  drafted_by_lace: boolean
  created_at: string
}

export interface OfferInput {
  title: string
  description?: string
  price_cents: number
  delivery: OfferDelivery
  delivery_url?: string | null
  delivery_note?: string
  status?: OfferStatus
}

export interface PayeeInput {
  label: string
  route: PayeeRoute
  /** Withdrawals only: near, base, eth, sol... */
  chain?: string | null
  address: string
  memo?: string | null
  /** Basis points of each sale: 10000 is all of it. */
  share_bps: number
}

export interface PayeeDto extends Required<Omit<PayeeInput, "chain" | "memo">> {
  id: string
  chain: string | null
  memo: string | null
}

const base = (laceId: string) => `/api/v1/laces/${laceId}/store`

/** The Lace's Store, or null before anyone turned it on. */
export function getStore(laceId: string): Promise<StoreDto | null> {
  return apiFetch(base(laceId))
}

/** Show or hide the Store's tab; the first time, this makes the Store. */
export function setStoreShown(laceId: string, shown: boolean): Promise<StoreDto> {
  return apiFetch(`${base(laceId)}/shown`, { method: "PUT", body: JSON.stringify({ shown }) })
}

export function updateStore(laceId: string, update: StoreUpdate): Promise<StoreDto> {
  return apiFetch(base(laceId), { method: "PATCH", body: JSON.stringify(update) })
}

export function listOffers(laceId: string): Promise<OfferDto[]> {
  return apiFetch(`${base(laceId)}/offers`)
}

export function addOffer(laceId: string, offer: OfferInput): Promise<OfferDto> {
  return apiFetch(`${base(laceId)}/offers`, { method: "POST", body: JSON.stringify(offer) })
}

export function updateOffer(laceId: string, offerId: string, update: Partial<OfferInput>): Promise<OfferDto> {
  return apiFetch(`${base(laceId)}/offers/${offerId}`, { method: "PATCH", body: JSON.stringify(update) })
}

export function listPayees(laceId: string): Promise<PayeeDto[]> {
  return apiFetch(`${base(laceId)}/payees`)
}

/** Replace the revenue split, while the Store is still being set up. */
export function setPayees(laceId: string, payees: PayeeInput[]): Promise<PayeeDto[]> {
  return apiFetch(`${base(laceId)}/payees`, { method: "PUT", body: JSON.stringify({ payees }) })
}

/** A passkey the owner registered on this site: public data only. */
export interface PasskeyOwner {
  credential_id: string
  /** P-256, SPKI, base64url. */
  public_key: string
  rp_id: string
  origin: string
}

export type StoreSignatureType = "agent_create" | "grant_issue" | "policy_update" | "agent_freeze" | "agent_unfreeze"
export type StoreSignatureStatus = "awaiting_signature" | "submitted" | "succeeded" | "failed" | "expired"

/** What the owner's passkey signs, unchanged, and what it means. */
export interface SignatureRequestDto {
  correlation_id: string
  type: StoreSignatureType
  /** For a passkey: { standard: "webauthn", payload: the WebAuthn request options }. */
  intent: { standard: string; payload: unknown } & Record<string, unknown>
  preview: { summary?: string } & Record<string, unknown>
  expires_at: string
}

export interface SignatureStatusDto {
  correlation_id: string
  type: StoreSignatureType
  status: StoreSignatureStatus
  failure_code: string | null
  store: StoreDto
}

/** The passkey that signs for the Store, before its wallet exists. Owner only. */
export function setStoreOwner(laceId: string, owner: PasskeyOwner): Promise<StoreDto> {
  return apiFetch(`${base(laceId)}/owner`, { method: "PUT", body: JSON.stringify(owner) })
}

/** The next request the owner signs to take the Store live. */
export function requestStoreSignature(laceId: string): Promise<SignatureRequestDto> {
  return apiFetch(`${base(laceId)}/signatures`, { method: "POST" })
}

export function submitStoreSignature(laceId: string, correlationId: string,
                                     signedData: Record<string, unknown>): Promise<SignatureStatusDto> {
  return apiFetch(`${base(laceId)}/signatures/${correlationId}`, {
    method: "POST", body: JSON.stringify({ signed_data: signedData }),
  })
}

export function getStoreSignature(laceId: string, correlationId: string): Promise<SignatureStatusDto> {
  return apiFetch(`${base(laceId)}/signatures/${correlationId}`)
}
