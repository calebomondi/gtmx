import { getAccessToken } from "@/lib/supabase"

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

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await getAccessToken()
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
  const token = await getAccessToken()
  const response = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  })
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
