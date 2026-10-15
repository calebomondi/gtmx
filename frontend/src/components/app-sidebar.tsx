"use client"

import * as React from "react"

import { NavMain } from "@/components/nav-main"
import { NavProjects } from "@/components/nav-projects"
import { NavSearchNew } from "@/components/nav-search-new"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  useSidebar,
  SidebarTrigger
} from "@/components/ui/sidebar"
import { Pin, Layers, LayoutGrid, Archive, LogInIcon } from "lucide-react"
import { Link } from "react-router-dom"
import { getCurrentUser, workspaceDisplayName } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import {
  ensureWorkspacesLoaded,
  toggleWorkspacePin,
  useWorkspaces,
} from "@/lib/workspaces-store"

// Static sidebar section (Extras nav links).
const data = {
  projects: [
    {
      name: "Accounts",
      url: "/accounts",
      icon: (
        <LayoutGrid
        />
      ),
    },
    // {
    //   name: "Industry Latest",
    //   url: "#",
    //   icon: (
    //     <Newspaper
    //     />
    //   ),
    // },
    // {
    //   name: "Bookmark",
    //   url: "#",
    //   icon: (
    //     <Bookmark
    //     />
    //   ),
    // },
    {
      name: "Archive",
      url: "/archive",
      icon: (
        <Archive
        />
      ),
    },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { state, toggleSidebar, isMobile } = useSidebar()
  // On phones the sidebar is a slide-over, always shown in full.
  const expanded = state === "expanded" || isMobile
  const { workspaces } = useWorkspaces()
  const { user: authUser } = useAuth()
  const [user, setUser] = React.useState<{
    name: string
    email: string
    avatar: string
  } | null>(null)

  React.useEffect(() => {
    ensureWorkspacesLoaded()
    let cancelled = false
    if (!authUser) {
      setUser(null)
      return
    }
    void getCurrentUser()
      .then((me) => {
        if (cancelled) return
        setUser({
          name: me.name ?? authUser.email ?? "User",
          email: me.email ?? "",
          avatar: me.avatar_url ?? "",
        })
      })
      .catch(() => {
        if (cancelled) return
        setUser({
          name:
            (authUser.user_metadata?.full_name as string | undefined) ??
            authUser.email ??
            "User",
          email: authUser.email ?? "",
          avatar: (authUser.user_metadata?.avatar_url as string | undefined) ?? "",
        })
      })
    return () => {
      cancelled = true
    }
  }, [authUser])

  const toNavItem = (workspace: (typeof workspaces)[number]) => ({
    id: workspace.id,
    title: workspaceDisplayName(workspace),
    url: `/workspace/${workspace.id}`,
    pinned: workspace.pinned,
  })

  const navMain = [
    {
      title: "Pinned",
      url: "#",
      icon: <Pin />,
      isActive: true,
      items: workspaces.filter((workspace) => workspace.pinned).map(toNavItem),
    },
    {
      title: "Workspaces",
      url: "#",
      icon: <Layers />,
      isActive: true,
      items: workspaces.map(toNavItem),
    },
  ]

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <div className={`flex items-center ${expanded ? 'justify-between' : 'justify-center'}`}>
          {expanded ? (
            <div className="ml-2.5 flex items-center justify-start space-x-1">
              <div className="h-4.5 w-4.5 rounded-xs bg-[#FEA853]" />
              <p className="text-2xl">Thalace</p>
            </div>
          ) : (
            // Collapsed, the mark itself opens the sidebar again.
            <button type="button" onClick={toggleSidebar} aria-label="Expand sidebar" className="ml-2.5 flex cursor-pointer items-center justify-center">
              <div className="h-5.5 w-5.5 rounded-xs bg-[#FEA853]" />
            </button>
          )}
          {expanded ? <SidebarTrigger className="-ml-1" /> : <></>}
        </div>
      </SidebarHeader>
      <SidebarContent>
        <NavSearchNew projects={data.projects} />
        <NavMain
          items={navMain}
          onTogglePin={(workspaceId) => void toggleWorkspacePin(workspaceId)}
        />
        <NavProjects projects={data.projects} />
      </SidebarContent>
      <SidebarFooter>
        {user ? (
          <NavUser user={user} />
        ) : (
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" render={<Link to="/auth/login" />}>
                <LogInIcon className="size-4" />
                <span>Sign in</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        )}
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
