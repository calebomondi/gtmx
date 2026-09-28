import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { SquarePen, Search, Home, FolderClosed } from "lucide-react"
import { useNavigate } from "react-router-dom"

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

  return (
    <SidebarGroup>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            tooltip="Home Feed"
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
