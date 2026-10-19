import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { SquarePen, Home } from "lucide-react"
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
            tooltip="New Lace"
            isActive={isNavItemActive(pathname, "/new")}
            className="cursor-pointer"
            onClick={() => navigate("/new")}
          >
            <SquarePen />
            <span>New Lace</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  )
}