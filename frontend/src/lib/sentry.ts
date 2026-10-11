import * as Sentry from "@sentry/react"

/** Browser error reporting. Off unless VITE_SENTRY_DSN is set. The SDK sends
 * no personal data (IPs, cookies) by default. */
export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN?.trim()
  if (!dsn) return
  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT?.trim() || import.meta.env.MODE,
  })
}
