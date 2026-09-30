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
import { answerDiscovery, useAgentRun } from "@/lib/agent-run-store"

import Workspace from './sidepanel/workspace'
import RecentSession from './sidepanel/recent_session'
import NewWorkspace from './sidepanel/new_workspace'
import { ThemeProvider } from "@/components/theme-provider"
import { ProjectsComponent } from "@/projects/projects-components"
import { ProjectHub } from "@/projects/project-hub"
import { ArchiveComponent } from "@/archive/archive-components"
import { ArchivedWorkspace } from "@/archive/archived-workspace"
import { HomeFeed } from "@/home-feed/home-feed-components"

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
      { path: 'archive/workspace/:workspace_id', element: <ArchivedWorkspace /> },
    ],
  },
])

function App() {
  return <RouterProvider router={router} />
}

export default App