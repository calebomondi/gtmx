// import {
//   DropdownMenu,
//   DropdownMenuContent,
//   DropdownMenuItem,
//   DropdownMenuSeparator,
//   DropdownMenuTrigger,
// } from "@/components/ui/dropdown-menu"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  // SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  // useSidebar,
} from "@/components/ui/sidebar"
// import { MoreHorizontalIcon, FolderIcon, ArrowRightIcon, Trash2Icon } from "lucide-react"
import { useLocation, useNavigate } from "react-router-dom"

import { isNavItemActive } from "@/lib/nav-active"

export function NavProjects({
  projects,
}: {
  projects: {
    name: string
    url: string
    icon: React.ReactNode
  }[]
}) {
  // const { isMobile } = useSidebar()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  // Internal routes navigate client-side so the app doesn't reload and refetch
  // every store; the placeholder "#" items keep their old anchor behaviour.
  const isInternal = (url: string) => url.startsWith("/")
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Extras</SidebarGroupLabel>
      <SidebarMenu>
        {projects.map((item) => (
          <SidebarMenuItem key={item.name}>
            <SidebarMenuButton
              render={
                isInternal(item.url) ? (
                  <a
                    href={item.url}
                    onClick={(event) => {
                      event.preventDefault()
                      navigate(item.url)
                    }}
                  />
                ) : (
                  <a href={item.url} />
                )
              }
              tooltip={item.name}
              isActive={isNavItemActive(pathname, item.url)}
            >
              {item.icon}
              <span>{item.name}</span>
            </SidebarMenuButton>
            {/* <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <SidebarMenuAction
                    showOnHover
                    className="aria-expanded:bg-muted"
                  />
                }
              >
                <MoreHorizontalIcon
                />
                <span className="sr-only">More</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-fit"
                side={isMobile ? "bottom" : "right"}
                align={isMobile ? "end" : "start"}
              >
                <DropdownMenuItem>
                  <FolderIcon
                  />
                  <span>View Project</span>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <ArrowRightIcon
                  />
                  <span>Share Project</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive">
                  <Trash2Icon
                  />
                  <span>Delete Project</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu> */}
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}
