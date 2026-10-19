import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { SquarePen, Search, Home } from "lucide-react"
import { useCallback, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"

import { LaceSearch } from "@/features/lace/lace-search"
import { useSearchShortcut } from "@/features/lace/use-lace-search"

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
  const [searchOpen, setSearchOpen] = useState(false)
  const toggleSearch = useCallback(() => setSearchOpen((open) => !open), [])
  useSearchShortcut(toggleSearch)

  return (
    <SidebarGroup>
      <LaceSearch open={searchOpen} onOpenChange={setSearchOpen} />
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
        <SidebarMenuItem>
          <SidebarMenuButton tooltip="Search (Ctrl+K)" className="cursor-pointer" onClick={() => setSearchOpen(true)}>
            <Search />
            <span>Search</span>
            <kbd className="ml-auto text-xs text-muted-foreground">Ctrl K</kbd>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  )
}