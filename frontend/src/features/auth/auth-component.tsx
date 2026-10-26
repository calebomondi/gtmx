import { AnimatePresence, motion } from "motion/react"
import { Navigate, useLocation } from "react-router-dom"

import { LoginForm } from "@/components/login-form"
import { SignupForm } from "@/components/signup-form"
import type { AuthMode } from "@/features/auth/auth-types"
import { useAuth } from "@/lib/auth"
import { usePageTitle } from "@/lib/use-page-title"

export default function AuthPage() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  const mode: AuthMode = pathname.endsWith("/signup") ? "signup" : "login"
  usePageTitle(mode === "signup" ? "Sign up" : "Sign in")

  if (user) return <Navigate to="/feed" replace />

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex items-center space-x-1 self-center">
          <div className="h-4.5 w-4.5 bg-[#FEA853] rounded-xs" />
          <p className="text-2xl">Thalace</p>
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={mode}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            {mode === "signup" ? <SignupForm /> : <LoginForm />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
