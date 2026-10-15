import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { TooltipProvider } from "@/components/ui/tooltip"
import { SessionProviderWithState } from "@/lib/session-context"
import { AuthProvider } from "@/lib/auth"
import { initSentry } from "@/lib/sentry"

initSentry()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TooltipProvider>
      <AuthProvider>
        <SessionProviderWithState>
          <App />
        </SessionProviderWithState>
      </AuthProvider>
    </TooltipProvider>
  </StrictMode>,
)
