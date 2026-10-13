import type { WaitlistSource } from './api'

const MAX = 100

/** Where this visitor came from: the link's UTM tags and the referring site. */
export function readSource(): WaitlistSource {
  const params = new URLSearchParams(window.location.search)
  const pick = (key: string) => params.get(key)?.slice(0, MAX) || undefined
  const referrer = document.referrer && !document.referrer.startsWith(window.location.origin)
    ? document.referrer.slice(0, 300)
    : undefined
  return {
    utm_source: pick('utm_source'),
    utm_medium: pick('utm_medium'),
    utm_campaign: pick('utm_campaign'),
    referrer,
  }
}
