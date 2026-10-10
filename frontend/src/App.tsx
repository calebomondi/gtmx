import { useEffect } from 'react'
import { createBrowserRouter, RouterProvider, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AppSidebar } from "@/components/app-sidebar"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { DiscoveryInterruptPicker } from "@/components/interrupt-panel"
import { answerDiscovery, resumeActiveDiscovery, useAgentRun } from "@/lib/agent-run-store"
import { useAuth } from "@/lib/auth"

import Workspace from './features/workspace/workspace'
import RecentSession from './features/workspace/recent-session'
import NewWorkspace from './features/workspace/new/new-workspace'
import { ThemeProvider } from "@/components/theme-provider"
import { ProjectsComponent } from "@/features/projects/projects-components"
import { ProjectHub } from "@/features/projects/project-hub"
import { ArchiveComponent } from "@/features/archive/archive-components"
import { AccountsComponent } from "@/features/connected-accounts/accounts-component"
import { ArchivedWorkspace } from "@/features/archive/archived-workspace"
import { HomeFeed } from "@/features/home-feed/home-feed-components"
import AuthPage from "@/features/auth/auth-component"
import AuthCallback from "@/features/auth/auth-callback"
import ForgotPasswordPage from "@/features/auth/forgot-password"
import UpdatePasswordPage from "@/features/auth/update-password"

/**
 * Interrupts surface inline inside the /new form's right-hand panel; on every
 * other route this dialog takes over so a discovery run is never stranded just
 * because the user navigated away mid-interview.
 */
function GlobalInterruptDialog() {
  const run = useAgentRun()
  const location = useLocation()

  const open =
    run.stage === "awaiting_input" &&
    run.currentInterrupt !== null &&
    location.pathname !== "/new"

  if (!open || !run.currentInterrupt) return null

  return (
    <Dialog open>
      <DialogContent
        className="sm:max-w-xl"
        showCloseButton={false}
      >
        <DialogHeader>
          <DialogTitle>The agent needs your input</DialogTitle>
          <DialogDescription>
            Answer the question to continue the discovery run.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-64 w-full items-center justify-center overflow-y-auto p-4">
          <DiscoveryInterruptPicker
            interrupt={run.currentInterrupt}
            fallbackProductName={run.currentInterrupt.offer_name ?? ""}
            fallbackUrl={run.currentInterrupt.url ?? ""}
            onAnswer={answerDiscovery}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

function AppLayout() {
  const { user } = useAuth()
  const location = useLocation()
  // Reattach to a discovery run that outlived the last page load (or was
  // started on another device). Runs live on the server; this only resumes
  // watching one.
  useEffect(() => {
    if (user) void resumeActiveDiscovery()
  }, [user])

  // Every app route needs a session; send visitors to sign in and back here.
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/auth/login?next=${next}`} replace />
  }

  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <SidebarProvider className="h-screen">
        <AppSidebar />
        <SidebarInset className="flex h-screen flex-col overflow-hidden">
          <Outlet />
          <GlobalInterruptDialog />
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
      { path: 'workspace', element: <Workspace /> },
      { path: 'workspace/:workspace_id', element: <Workspace /> },
      { path: 'recent', element: <RecentSession /> },
      { path: 'new', element: <NewWorkspace /> },
      { path: 'projects', element: <ProjectsComponent /> },
      { path: 'projects/:project_id', element: <ProjectHub /> },
      {
        path: 'projects/:project_id/workspace/:workspace_id',
        element: <ProjectHub />,
      },
      { path: 'feed', element: <HomeFeed /> },
      { path: 'archive', element: <ArchiveComponent /> },
      { path: 'accounts', element: <AccountsComponent /> },
      { path: 'archive/workspace/:workspace_id', element: <ArchivedWorkspace /> },
    ],
  },
])

function App() {
  return <RouterProvider router={router} />
}

export default App