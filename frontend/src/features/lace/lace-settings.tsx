import { ChevronRight } from "lucide-react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Separator } from "@/components/ui/separator"
import type { FactDto, LaceStatus } from "@/lib/api"

import { LaceBrief } from "./lace-brief"
import { LaceFacts } from "./lace-facts"
import { LaceManage } from "./lace-manage"

/** A Lace's settings and memory: when it posts its brief, everything it
 * knows about the startup (each fact with its source), and archiving or
 * deleting it. */
export function LaceSettings({ laceId, name, status, facts, open, onOpenChange, onChanged }: {
  laceId: string
  name: string
  status: LaceStatus
  facts: FactDto[]
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The Lace was archived or restored. */
  onChanged: () => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{name}'s settings</SheetTitle>
          <SheetDescription>Its brief, what it knows about your startup, and archiving or deleting it.</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-6 px-4 pb-6">
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Brief</h3>
            <LaceBrief laceId={laceId} />
          </section>
          <Separator />
          {/* Closed by default: a long list would push Manage out of sight. */}
          <Collapsible render={<section className="group/knows flex flex-col gap-3" />}>
            <CollapsibleTrigger className="flex cursor-pointer items-center justify-between gap-2 text-left text-sm font-medium">
              What {name} knows ({facts.length})
              <ChevronRight className="size-4 text-muted-foreground transition-transform group-data-open/knows:rotate-90" />
            </CollapsibleTrigger>
            <p className="text-xs text-muted-foreground">Learned from your site, its research and you. Each fact keeps its source.</p>
            <CollapsibleContent>
              <LaceFacts facts={facts} />
            </CollapsibleContent>
          </Collapsible>
          <Separator />
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Manage</h3>
            <LaceManage laceId={laceId} name={name} status={status} onChanged={onChanged} />
          </section>
        </div>
      </SheetContent>
    </Sheet>
  )
}
