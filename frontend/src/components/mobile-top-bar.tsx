import { SidebarTrigger } from '@/components/ui/sidebar'

/** On phones the sidebar is a slide-over with nothing on screen to open it;
 * this bar holds its menu button for pages without a header of their own. */
export function MobileTopBar() {
  return (
    <header className="sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur md:hidden">
      <SidebarTrigger aria-label="Open menu" />
      <span className="flex items-center gap-1.5">
        <span aria-hidden className="size-4 rounded-xs bg-[#FEA853]" />
        <span className="text-xl leading-none">Thalace</span>
      </span>
    </header>
  )
}
