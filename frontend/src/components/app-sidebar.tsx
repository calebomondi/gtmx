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
import { Pin, Archive, Layers, LayoutGrid, LogInIcon } from "lucide-react"
import { Link } from "react-router-dom"
import { Lace } from "@/components/lace-mascot"
import { getCurrentUser, type LaceListItemDto } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import {
  ensureLacesLoaded,
  refetchLaces,
  sidebarMascot,
  toggleLacePin,
  useLaces,
} from "@/lib/laces-store"

// How often the sidebar refreshes each Lace's mood (working, waiting on you).
const LACES_REFRESH_MS = 30_000
// Sidebar mascots are drawn at this size, in their simplified small face.
const MASCOT_PX = 16

// Static sidebar section (Extras nav links).
const data = {
  projects: [
    {
      name: "Shared accounts",
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
  ],
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { state, toggleSidebar, isMobile } = useSidebar()
  // On phones the sidebar is a slide-over, always shown in full.
  const expanded = state === "expanded" || isMobile
  const { laces, archived } = useLaces()
  const { user: authUser } = useAuth()
  const [user, setUser] = React.useState<{
    name: string
    email: string
    avatar: string
  } | null>(null)

  React.useEffect(() => {
    if (!authUser) return
    ensureLacesLoaded()
    const timer = setInterval(() => void refetchLaces(), LACES_REFRESH_MS)
    return () => clearInterval(timer)
  }, [authUser])

  React.useEffect(() => {
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

  const toNavItem = (section: "pinned" | "all") => (lace: LaceListItemDto, index: number) => ({
    id: lace.id,
    title: lace.name,
    url: `/lace/${lace.id}`,
    pinned: lace.pinned,
    icon: <Lace state={sidebarMascot(lace, section, index)} size={MASCOT_PX} phase={index * 1.3} decorative />,
  })

  const navMain = [
    {
      title: "Pinned",
      url: "#",
      icon: <Pin />,
      isActive: true,
      items: laces.filter((lace) => lace.pinned).map(toNavItem("pinned")),
    },
    {
      title: "Laces",
      url: "#",
      icon: <Layers />,
      isActive: true,
      items: laces.map(toNavItem("all")),
    },
    // Only when there are some, and closed: they do no work.
    ...(archived.length > 0 ? [{
      title: "Archived",
      url: "#",
      icon: <Archive />,
      isActive: false,
      items: archived.map((lace) => ({
        id: lace.id,
        title: lace.name,
        url: `/lace/${lace.id}`,
        icon: <Lace state="sleepy" size={MASCOT_PX} decorative />,
      })),
    }] : []),
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
          // A failed pin is rolled back and kept as the store error.
          onTogglePin={(laceId) => void toggleLacePin(laceId).catch(() => undefined)}
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
