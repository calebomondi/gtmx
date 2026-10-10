import { createContext, useContext, useEffect, useMemo, useState } from "react"
import type { Session, User } from "@supabase/supabase-js"

import { supabase } from "@/lib/supabase"
import { clearCurrentUserCache } from "@/lib/api"

interface AuthContextValue {
  user: User | null
  session: Session | null
  loading: boolean
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  session: null,
  loading: true,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    void supabase.auth.getSession().then(({ data }) => {
      if (cancelled) return
      setSession(data.session)
      setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s)
      clearCurrentUserCache()
      setLoading(false)
    })
    return () => {
      cancelled = true
      sub.subscription.unsubscribe()
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user: session?.user ?? null, session, loading }),
    [session, loading],
  )
  // Don't render children until the initial session restore resolves:
  // otherwise mount-time callers (app-sidebar, workspaces-store) would fire
  // /users/me etc. before the access token exists, get 401s, and leave those
  // stores empty.
  if (loading) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-muted">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext)
}
