import { Toaster } from 'sonner'
import { createBrowserRouter, RouterProvider, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AppSidebar } from "@/components/app-sidebar"
import { MobileTopBar } from "@/components/mobile-top-bar"
import { backdropMood, backdropTone } from "@/components/backdrop-tone"
import { PageBackdrop } from "@/components/page-backdrop"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import { useAuth } from "@/lib/auth"
import { useLaces } from "@/lib/laces-store"
import { useActivityHeartbeat } from "@/lib/use-activity-heartbeat"

import { ThemeProvider } from "@/components/theme-provider"
import { AccountsComponent } from "@/features/connected-accounts/accounts-component"
import LaceList from "@/features/lace/lace-list"
import NewLace from "@/features/lace/new-lace"
import LaceSetup from "@/features/lace/lace-setup"
import LaceWorkspace from "@/features/lace/lace-workspace"
import LaceHomeFeed from "@/features/lace/lace-home-feed"
import AuthPage from "@/features/auth/auth-component"
import AuthCallback from "@/features/auth/auth-callback"
import ForgotPasswordPage from "@/features/auth/forgot-password"
import UpdatePasswordPage from "@/features/auth/update-password"

// Below laptop width the expanded sidebar (16rem) squeezes the page, so it
// starts as icons there; the user's toggle still wins for the session.
const SIDEBAR_EXPANDED_FROM = 1024
const sidebarOpenByDefault = () => typeof window === 'undefined' || window.innerWidth >= SIDEBAR_EXPANDED_FROM

function AppLayout() {
  const { user } = useAuth()
  const { laces } = useLaces()
  const location = useLocation()
  useActivityHeartbeat(Boolean(user))

  // Every app route needs a session; send visitors to sign in and back here.
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/auth/login?next=${next}`} replace />
  }

  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <SidebarProvider className="h-dvh" defaultOpen={sidebarOpenByDefault()}>
        <AppSidebar />
        <SidebarInset className="isolate flex h-dvh min-w-0 flex-col overflow-hidden">
          <PageBackdrop tone={backdropTone(location.pathname)} mood={backdropMood(location.pathname, laces)} />
          <MobileTopBar />
          <Outlet />
          <Toaster position="bottom-right" richColors closeButton />
        </SidebarInset>
      </SidebarProvider>
    </ThemeProvider>
  )
}

const router = createBrowserRouter([
  { path: '/auth', element: <Navigate to="/auth/login" replace /> },
  { path: '/auth/callback', element: <AuthCallback /> },
  {
    path: '/auth/forgot-password',
    element: (
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <ForgotPasswordPage />
      </ThemeProvider>
    ),
  },
  {
    path: '/auth/update-password',
    element: (
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <UpdatePasswordPage />
      </ThemeProvider>
    ),
  },
  {
    path: '/auth/login',
    element: (
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <AuthPage />
      </ThemeProvider>
    ),
  },
  {
    path: '/auth/signup',
    element: (
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <AuthPage />
      </ThemeProvider>
    ),
  },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/feed" replace /> },
      { path: 'new', element: <NewLace /> },
      { path: 'feed', element: <LaceHomeFeed /> },
      { path: 'lace', element: <LaceList /> },
      { path: 'lace/new', element: <Navigate to="/new" replace /> },
      { path: 'lace/:lace_id', element: <LaceWorkspace /> },
      { path: 'lace/:lace_id/setup', element: <LaceSetup /> },
      { path: 'lace/:lace_id/:tab', element: <LaceWorkspace /> },
      { path: 'accounts', element: <AccountsComponent /> },
    ],
  },
])

function App() {
  return <RouterProvider router={router} />
}

export default App