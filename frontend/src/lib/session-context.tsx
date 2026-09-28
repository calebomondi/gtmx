import { useMemo, useState } from "react"

import type { OfferSnapshot } from "@/lib/api"
import { getStrictContext } from "@/lib/get-strict-context"

export interface ConfirmedSession {
  sessionId: string | null
  workspaceId: string | null
  product: OfferSnapshot | null
}

export interface SessionContextValue extends ConfirmedSession {
  setSession: (session: ConfirmedSession) => void
  clearSession: () => void
}

const [SessionProvider, useSafeSessionContext] =
  getStrictContext<SessionContextValue>("SessionProvider")

export function SessionProviderWithState({
  children,
}: {
  children: React.ReactNode
}) {
  const [session, setSessionState] = useState<ConfirmedSession>({
    sessionId: null,
    workspaceId: null,
    product: null,
  })

  const value = useMemo<SessionContextValue>(
    () => ({
      ...session,
      setSession: setSessionState,
      clearSession: () =>
        setSessionState({ sessionId: null, workspaceId: null, product: null }),
    }),
    [session],
  )

  return <SessionProvider value={value}>{children}</SessionProvider>
}

export function useSession(): SessionContextValue {
  return useSafeSessionContext()
}