import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { TooltipProvider } from "@/components/ui/tooltip"
import { SessionProviderWithState } from "@/lib/session-context"

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TooltipProvider>
      <SessionProviderWithState>
        <App />
      </SessionProviderWithState>
    </TooltipProvider>
  </StrictMode>,
)
