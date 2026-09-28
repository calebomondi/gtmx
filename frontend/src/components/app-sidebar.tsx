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
import { Pin, Layers, LayoutGrid, Newspaper, Bookmark} from "lucide-react"
import { getCurrentUser, workspaceDisplayName } from "@/lib/api"
import {
  ensureWorkspacesLoaded,
  toggleWorkspacePin,
  useWorkspaces,
} from "@/lib/workspaces-store"

// Static sidebar section (Extras nav links).
const data = {
  projects: [
    {
      name: "Showcase",
      url: "#",
      icon: (
        <LayoutGrid
        />
      ),
    },
    {
      name: "Industry Latest",
      url: "#",
      icon: (
        <Newspaper
        />
      ),
    },
    {
      name: "Bookmark",
      url: "#",
      icon: (
        <Bookmark
        />
      ),
    },
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { state } = useSidebar()
  const { workspaces } = useWorkspaces()
  const [user, setUser] = React.useState<{
    name: string
    email: string
    avatar: string
  } | null>(null)

  React.useEffect(() => {
    ensureWorkspacesLoaded()
    let cancelled = false
    void getCurrentUser()
      .then((me) => {
        if (cancelled) return
        console.log(`>> ${me.name}`)
        setUser({ name: me.name, email: me.email, avatar: me.avatar_url ?? "" })
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

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
        {user && <NavUser user={user} />}
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
