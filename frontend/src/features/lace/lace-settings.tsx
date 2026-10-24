import { ChevronRight } from "lucide-react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Separator } from "@/components/ui/separator"
import type { FactDto, LaceStatus } from "@/lib/api"

import { LaceAppsSection } from "./lace-apps"
import { LaceBrief } from "./lace-brief"
import { LaceDocuments } from "./lace-documents"
import { LaceFacts } from "./lace-facts"
import { LaceManage } from "./lace-manage"
import { LaceWatch } from "./lace-watch"
import type { LaceApps } from "./use-lace-apps"
import { useLaceBrief } from "./use-lace-brief"

/** A Lace's settings and memory: how often it keeps watch, when it posts
 * its brief, everything it knows about the startup (each fact with its
 * source), and archiving or deleting it. */
export function LaceSettings({ laceId, name, status, facts, apps, open, onOpenChange, onChanged }: {
  laceId: string
  name: string
  status: LaceStatus
  facts: FactDto[]
  apps: LaceApps
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The Lace was archived or restored. */
  onChanged: () => void
}) {
  const schedule = useLaceBrief(laceId)
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{name}'s settings</SheetTitle>
          <SheetDescription>
            How often it keeps watch, its brief, the apps it works in, what it knows about your startup, and archiving or
            deleting it.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-6 px-4 pb-6">
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Keeping watch</h3>
            <LaceWatch name={name} schedule={schedule} />
          </section>
          <Separator />
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Brief</h3>
            <LaceBrief schedule={schedule} />
          </section>
          <Separator />
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Apps &amp; accounts</h3>
            <p className="text-xs text-muted-foreground">
              The apps {name} works in. It acts in them only when you approve, and only in the ones switched on here.
            </p>
            <LaceAppsSection laceId={laceId} name={name} apps={apps} />
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
            <h3 className="text-sm font-medium">Documents</h3>
            <p className="text-xs text-muted-foreground">What you shared with {name} in the chat. It reads them when they matter.</p>
            <LaceDocuments laceId={laceId} name={name} />
          </section>
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
