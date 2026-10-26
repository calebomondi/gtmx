import { Lock, Users } from "lucide-react"

import { Tabs, TabsIndicator, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { ChatThread } from "@/lib/api"
import { cn } from "@/lib/utils"

/** On a Lace with a team: the team's chat, or the founder's own private one. */
export function ChatThreadSwitch({ value, onChange }: { value: ChatThread; onChange: (next: ChatThread) => void }) {
  return (
    <Tabs value={value} onValueChange={(next) => onChange(next as ChatThread)} className="items-center gap-0">
      <TabsList aria-label="Which chat"
                className="relative group-data-horizontal/tabs:h-auto gap-0.5 rounded-full border bg-muted/70 p-1 backdrop-blur-md">
        <TabsIndicator className={cn("top-(--active-tab-top) left-(--active-tab-left) h-(--active-tab-height) w-(--active-tab-width)",
                                     "rounded-full bg-background shadow-sm ring-1 ring-theme/40 transition-all duration-300 ease-out")} />
        {([["team", "Team chat", Users], ["mine", "Just you", Lock]] as const).map(([thread, label, Icon]) => (
          <TabsTrigger key={thread} value={thread}
                       className={cn("relative z-[1] h-7 flex-none gap-1.5 rounded-full px-3.5 text-xs text-muted-foreground",
                                     "hover:text-foreground data-active:bg-transparent data-active:font-medium data-active:text-foreground data-active:shadow-none",
                                     "dark:data-active:bg-transparent")}>
            <Icon className="size-3.5" /> {label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
