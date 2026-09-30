import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar"
import { ChevronRightIcon, PinIcon, PinOffIcon } from "lucide-react"
import { Link, useLocation } from "react-router-dom"

import { isWorkspaceActive } from "@/lib/nav-active"

export interface NavWorkspaceItem {
  id: string
  title: string
  url: string
  pinned: boolean
}

export function NavMain({
  items,
  onTogglePin,
}: {
  items: {
    title: string
    url: string
    icon?: React.ReactNode
    isActive?: boolean
    items?: NavWorkspaceItem[]
  }[]
  onTogglePin?: (workspaceId: string) => void
}) {
  const location = useLocation()

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Campaigns</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => (
          <Collapsible
            key={item.title}
            defaultOpen={item.isActive}
            className="group/collapsible"
            render={<SidebarMenuItem />}
          >
            <CollapsibleTrigger
              render={<SidebarMenuButton tooltip={item.title} />}
            >
              {item.icon}
              <span>{item.title}</span>
              <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-open/collapsible:rotate-90" />
            </CollapsibleTrigger>
            <CollapsibleContent>
              <SidebarMenuSub>
                {item.items?.map((subItem) => (
                  <SidebarMenuSubItem
                    key={subItem.id}
                    className="group/subitem rounded-sm"
                  >
                    <SidebarMenuSubButton
                      render={<Link to={subItem.url} />}
                      isActive={isWorkspaceActive(location.pathname, subItem.id)}
                      className="min-w-0 flex-1"
                    >
                      <span className="truncate">{subItem.title}</span>
                      {onTogglePin && (
                        <button
                          type="button"
                          aria-label={
                            subItem.pinned ? "Unpin workspace" : "Pin workspace"
                          }
                          title={
                            subItem.pinned ? "Unpin workspace" : "Pin workspace"
                          }
                          onClick={(event) => {
                            event.preventDefault()
                            event.stopPropagation()
                            onTogglePin(subItem.id)
                          }}
                          className="ml-auto shrink-0 cursor-pointer rounded-xs p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:opacity-100 group-hover/subitem:opacity-100"
                        >
                          {subItem.pinned ? (
                            <PinOffIcon className="size-3" />
                          ) : (
                            <PinIcon className="size-3" />
                          )}
                        </button>
                      )}
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                ))}
                {item.items?.length === 0 && (
                  <SidebarMenuSubItem className="text-xs text-muted-foreground">
                    None yet
                  </SidebarMenuSubItem>
                )}
              </SidebarMenuSub>
            </CollapsibleContent>
          </Collapsible>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}
