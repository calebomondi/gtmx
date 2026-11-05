import { createClient } from "@supabase/supabase-js"

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)

/** Refresh a token this close to expiry before using it: a tab that slept can hold one already past it. */
const EXPIRY_MARGIN_MS = 60_000

/** The signed-in user's access token, refreshed first when it is about to expire; null when signed out. */
export async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession()
  const session = data.session
  if (!session) return null
  const expiresAt = (session.expires_at ?? 0) * 1000
  if (expiresAt - Date.now() < EXPIRY_MARGIN_MS) return refreshAccessToken()
  return session.access_token
}

/** A new access token from the session's refresh token; null when the session can't be renewed (signed out). */
export async function refreshAccessToken(): Promise<string | null> {
  const { data, error } = await supabase.auth.refreshSession()
  return error ? null : data.session?.access_token ?? null
}
