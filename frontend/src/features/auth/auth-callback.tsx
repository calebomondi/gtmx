import { useEffect } from "react"
import { useNavigate } from "react-router-dom"

import { supabase } from "@/lib/supabase"
import { safeNextPath, takeOAuthNext } from "@/lib/validation"

export default function AuthCallback() {
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      const url = new URL(window.location.href)
      const code = url.searchParams.get("code")
      const nextParam = url.searchParams.get("next")
      const isRecoveryHash = window.location.hash.includes("type=recovery")

      if (code) {
        try {
          await supabase.auth.exchangeCodeForSession(code)
        } catch {
          // fall through to session check
        }
      }
      const { data } = await supabase.auth.getSession()
      if (cancelled) return
      if (!data.session) {
        navigate("/auth/login", { replace: true })
        return
      }
      if (isRecoveryHash || nextParam === "/auth/update-password") {
        navigate("/auth/update-password", { replace: true })
        return
      }
      navigate(safeNextPath(nextParam) ?? takeOAuthNext() ?? "/feed", {
        replace: true,
      })
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [navigate])

  return (
    <div className="flex min-h-svh items-center justify-center bg-muted">
      <p className="text-sm text-muted-foreground">Signing you in…</p>
    </div>
  )
}
