import { createClient } from "@supabase/supabase-js"

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)

export async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}
