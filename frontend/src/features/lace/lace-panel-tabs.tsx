import type { ReactNode } from "react"
import { Loader2, type LucideIcon } from "lucide-react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

import type { LaceSection } from "./lace-activity-actions"

export interface PanelTab<S extends LaceSection> {
  value: S
  label: string
  icon: LucideIcon
  /** How many it holds; left out when there is no count worth showing. */
  count?: number
  /** How many wait on the founder: shown in the theme colour, over `count`. */
  waiting?: number
  /** The Lace is working on it in the background. */
  busy?: boolean
  content: ReactNode
}

function Tally({ tab }: { tab: PanelTab<LaceSection> }) {
  if (tab.busy) return <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-label="Working on it" />
  if (tab.waiting) {
    return (
      <span className="grid h-5 min-w-5 place-items-center rounded-full bg-theme px-1.5 text-[11px] font-medium text-neutral-900 tabular-nums"
            aria-label={`${tab.waiting} waiting on you`}>
        {tab.waiting > 99 ? "99+" : tab.waiting}
      </span>
    )
  }
  if (tab.count === undefined) return null
  return <span className="text-xs font-normal text-muted-foreground tabular-nums">{tab.count}</span>
}

/** A Feed or Messaging page: an optional header, then a row of sub-tabs that
 * stays in view while the open one scrolls. Only the open tab is mounted. */
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
      <div className="sticky top-0 z-10 mt-2 border-b bg-background/90 backdrop-blur">
        <TabsList variant="line" aria-label={label}
                  className="mx-auto flex h-12 w-full max-w-4xl justify-start gap-1 overflow-x-auto px-3 [scrollbar-width:none]">
          {tabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}
                         className={cn("h-full flex-none gap-2 px-3 data-active:text-foreground",
                                       "group-data-horizontal/tabs:after:bottom-[-4px] after:bg-theme")}>
              <tab.icon />
              {tab.label}
              <Tally tab={tab} />
            </TabsTrigger>
          ))}
        </TabsList>
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
