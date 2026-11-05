import { getAccessToken, refreshAccessToken } from "@/lib/supabase"

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

// The longest the app waits out "too many requests" before trying once more;
// a longer wait (a daily limit) is shown to the founder instead.
const MAX_RETRY_WAIT_S = 15

/** Send with the user's token; when the API refuses it (expired, revoked), renew it once and send again. */
async function fetchAuthed(path: string, init: RequestInit, headers: (token: string | null) => HeadersInit): Promise<Response> {
  const token = await getAccessToken()
  const response = await sendPaced(path, { ...init, headers: headers(token) })
  if (response.status !== 401 || !token) return response
  const renewed = await refreshAccessToken()
  return renewed ? sendPaced(path, { ...init, headers: headers(renewed) }) : response
}

/** Send; when the API says too many requests for a short while (429 with a
 * Retry-After), wait that long and send once more. A 429 means the API did
 * nothing, so a write is safe to send again too. */
async function sendPaced(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${path}`, init)
  const wait = Number(response.headers.get("Retry-After"))
  if (response.status !== 429 || !(wait > 0) || wait > MAX_RETRY_WAIT_S) return response
  await new Promise((resolve) => setTimeout(resolve, wait * 1000))
  if (init.signal?.aborted) return response
  return fetch(`${API_BASE}${path}`, init)
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetchAuthed(path, init, (token) => ({
    // A FormData body (a file upload) sets its own multipart boundary.
    ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...init.headers,
  }))

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

/**
 * Read a newline-delimited JSON stream (e.g. a run's events), calling `onItem`
 * for each line until the server ends it or `signal` aborts. A streaming fetch
 * rather than EventSource, because EventSource cannot send the auth header.
 */
export async function apiStream<T>(
  path: string,
  onItem: (item: T) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetchAuthed(path, { signal }, (token): HeadersInit => (token ? { Authorization: `Bearer ${token}` } : {}))
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, `${response.status} ${response.statusText}`)
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffered = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffered += value
    const lines = buffered.split("\n")
    buffered = lines.pop() ?? ""
    for (const line of lines) {
      if (line.trim()) onItem(JSON.parse(line) as T)
    }
  }
  if (buffered.trim()) onItem(JSON.parse(buffered) as T)
}
