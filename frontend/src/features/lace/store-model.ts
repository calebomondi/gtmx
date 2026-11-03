import type { OfferDelivery, OfferStatus, PayeeInput, StoreStatus } from "@/lib/api"

export const STORE_STATUS_LABEL: Record<StoreStatus, string> = {
  setup: "Being set up: nothing on sale yet",
  live: "Live: selling",
  paused: "Paused: no new checkouts",
}

export const STORE_STATUS_BADGE: Record<StoreStatus, string> = { setup: "Setting up", live: "Live", paused: "Paused" }

export const OFFER_STATUS_LABEL: Record<OfferStatus, string> = { draft: "Draft", active: "On sale", archived: "Archived" }

export const DELIVERY_LABEL: Record<OfferDelivery, string> = {
  link: "A private link, emailed once paid",
  service: "A service your team delivers",
}

/** Storefronts are served by this app, at /s/<slug>. */
export const STOREFRONT_PREFIX = `${window.location.host}/s/`

/** A whole sale, in basis points. */
export const FULL_SHARE_BPS = 10_000

/** "$29" or "$29.50". */
export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(cents % 100 ? 2 : 0)}`
}

/** "29.50" typed by a person, as whole cents; null when it isn't a price. */
export function centsFrom(text: string): number | null {
  const match = /^\s*\$?\s*(\d{1,6})(?:\.(\d{1,2}))?\s*$/.exec(text)
  if (!match) return null
  return Number(match[1]) * 100 + Number((match[2] ?? "0").padEnd(2, "0"))
}

/** "70%" or "12.5%". */
export function formatShare(bps: number): string {
  const percent = bps / 100
  return `${Number.isInteger(percent) ? percent : percent.toFixed(2).replace(/0$/, "")}%`
}

/** What no payee takes stays in the Store's wallet: its operating balance. */
export function keptShare(payees: Pick<PayeeInput, "share_bps">[]): number {
  return FULL_SHARE_BPS - payees.reduce((sum, p) => sum + p.share_bps, 0)
}
