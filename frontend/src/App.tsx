import { createBrowserRouter, RouterProvider, Navigate, Outlet } from 'react-router-dom';
import { AppSidebar } from "@/components/app-sidebar"
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar"

import Workspace from './sidepanel/workspace'
import RecentSession from './sidepanel/recent_session'
import NewWorkspace from './sidepanel/new_workspace'
import { ThemeProvider } from "@/components/theme-provider"

function AppLayout() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
      <SidebarProvider className="h-screen">
        <AppSidebar />
        <SidebarInset className="flex h-screen flex-col overflow-hidden">
          <Outlet />
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
      { path: 'feed', element: <RecentSession /> },
      { path: 'new', element: <NewWorkspace /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />
}
