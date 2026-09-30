import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { SquarePen, Search, Home, FolderClosed } from "lucide-react"
import { useLocation, useNavigate } from "react-router-dom"

import { isNavItemActive } from "@/lib/nav-active"

export function NavSearchNew({
  projects: _projects,
}: {
  projects: {
    name: string
    url: string
    icon: React.ReactNode
  }[]
}) {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  // Search Anything is deliberately left inactive: it is a placeholder that
  // routes to /feed, so matching it would light up alongside Home Feed.
  return (
    <SidebarGroup>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            tooltip="Home Feed"
            isActive={isNavItemActive(pathname, "/feed")}
            className="cursor-pointer"
            onClick={() => navigate("/feed")}
          >
            <Home />
            <span>Home Feed</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            tooltip="New"
            isActive={isNavItemActive(pathname, "/new")}
            className="cursor-pointer"
            onClick={() => navigate("/new")}
          >
            <SquarePen />
            <span>New Workspace</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton 
            tooltip="Search" 
            className="cursor-pointer"
            onClick={() => navigate("/feed")}
          >
            <Search />
            <span>Search Anything</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton 
            tooltip="Search" 
            isActive={isNavItemActive(pathname, "/projects")}
            className="cursor-pointer"
            onClick={() => navigate("/projects")}
          >
            <FolderClosed />
            <span>Projects</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  )
}