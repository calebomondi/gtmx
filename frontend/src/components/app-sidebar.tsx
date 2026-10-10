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
  const { state } = useSidebar()
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
        <div className={`flex items-center ${state === "expanded" ? 'justify-between' : 'justify-center'}`}>
          <div className={`flex items-center ml-2.5 space-x-1 ${state === "expanded" ? 'justify-start' : 'justify-center'}`}>
            <div className={`${state === "expanded" ? "h-4.5 w-4.5" : "h-5.5 w-5.5"} bg-[#FEA853] rounded-xs`}/>
            {state === "expanded" && <p className="text-2xl">gtmx</p>}
          </div>
          {state === "expanded" ? <SidebarTrigger className="-ml-1" /> : <></>}
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
