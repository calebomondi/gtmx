import type { ReactNode } from "react"
import { Loader2 } from "lucide-react"

import { Tabs, TabsContent, TabsIndicator, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

import type { LaceSection } from "./lace-activity-actions"

export interface PanelTab<S extends LaceSection> {
  value: S
  label: string
  /** How many it holds; left out when there is no count worth showing. */
  count?: number
  /** How many wait on the founder: shown in the theme colour, over `count`. */
  waiting?: number
  /** The Lace is working on it in the background. */
  busy?: boolean
  content: ReactNode
}

function Tally({ tab }: { tab: PanelTab<LaceSection> }) {
  if (tab.busy) return <Loader2 className="size-3 animate-spin text-theme" aria-label="Working on it" />
  if (tab.waiting) {
    return (
      <span className="grid h-4.5 min-w-4.5 place-items-center rounded-full bg-theme px-1 text-[10px] font-semibold text-neutral-900 tabular-nums"
            aria-label={`${tab.waiting} waiting on you`}>
        {tab.waiting > 99 ? "99+" : tab.waiting}
      </span>
    )
  }
  if (tab.count === undefined) return null
  return <span className="text-[11px] font-normal text-muted-foreground tabular-nums">{tab.count}</span>
}

/** A Feed or Messaging page: an optional header, then its sub-tabs as a
 * segmented control (a highlight slides to the open one) that stays in view
 * while the open tab scrolls. Only the open tab is mounted. */
export function LacePanelTabs<S extends LaceSection>({ label, tabs, value, onChange, header }: {
  label: string
  tabs: PanelTab<S>[]
  value: S
  onChange: (next: S) => void
  header?: ReactNode
}) {
  return (
    <Tabs value={value} onValueChange={(next) => onChange(next as S)} className="gap-0">
      {header && <div className="mx-auto w-full max-w-4xl px-4 pt-6">{header}</div>}
      <div className="sticky top-0 z-10 py-3">
        <div className="mx-auto w-full max-w-4xl px-4">
          <TabsList aria-label={label}
                    className="relative max-w-full justify-start group-data-horizontal/tabs:h-auto gap-0.5 overflow-x-auto rounded-full border bg-muted/70 p-1 backdrop-blur-md [scrollbar-width:none]">
            <TabsIndicator className={cn("top-(--active-tab-top) left-(--active-tab-left) h-(--active-tab-height) w-(--active-tab-width)",
                                         "rounded-full bg-background shadow-sm ring-1 ring-theme/40 transition-all duration-300 ease-out")} />
            {tabs.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}
                           className={cn("relative z-[1] h-8 flex-none gap-1.5 rounded-full px-4 text-[13px] text-muted-foreground",
                                         "hover:text-foreground data-active:bg-transparent data-active:font-medium data-active:text-foreground data-active:shadow-none",
                                         "dark:data-active:bg-transparent")}>
                {tab.label}
                <Tally tab={tab} />
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
      </div>
      {tabs.map((tab) => (
        <TabsContent key={tab.value} value={tab.value} className="mx-auto w-full max-w-4xl px-4 py-5">
          {tab.content}
        </TabsContent>
      ))}
    </Tabs>
  )
}

/** The line under the tabs that says what this one holds, with room for an
 * action on the right. */
export function PanelIntro({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm text-muted-foreground">{children}</p>
      {action}
    </div>
  )
}
