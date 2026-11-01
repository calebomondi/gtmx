import { ChevronRight } from "lucide-react"

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Separator } from "@/components/ui/separator"
import type { FactDto, LaceRole, LaceStatus } from "@/lib/api"

import { LaceAppsSection } from "./lace-apps"
import { LaceBrief } from "./lace-brief"
import { LaceBriefApps } from "./lace-brief-apps"
import { LaceDocuments } from "./lace-documents"
import { LaceFacts } from "./lace-facts"
import { LaceJurisdiction } from "./lace-jurisdiction"
import { LaceManage } from "./lace-manage"
import { LaceWatch } from "./lace-watch"
import type { LaceApps } from "./use-lace-apps"
import { useLaceBrief } from "./use-lace-brief"
import type { LaceRegulations } from "./use-lace-regulations"

/** A Lace's settings and memory: how often it keeps watch, when it posts
 * its brief, everything it knows about the startup (each fact with its
 * source), and archiving or deleting it. */
export function LaceSettings({ laceId, name, status, role, facts, apps, regulations, open, onOpenChange, onChanged }: {
  laceId: string
  name: string
  status: LaceStatus
  /** The person's role: members see what admins set, without changing it. */
  role: LaceRole
  facts: FactDto[]
  apps: LaceApps
  regulations: LaceRegulations
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The Lace was archived or restored. */
  onChanged: () => void
}) {
  const schedule = useLaceBrief(laceId)
  const manages = role !== "member"
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{name}'s settings</SheetTitle>
          <SheetDescription>
            How often it keeps watch, its brief, the apps it works in, where you operate, what it knows about your
            startup, and archiving or deleting it.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-6 px-4 pb-6">
          {!manages && (
            <p className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Its admins and owner change how {name} keeps watch, its brief and its apps. You can see them here.
            </p>
          )}
          {/* A disabled fieldset turns off every control in it, for members. */}
          <fieldset disabled={!manages} className="flex min-w-0 flex-col gap-6">
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Keeping watch</h3>
            <LaceWatch name={name} schedule={schedule} />
          </section>
          <Separator />
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Brief</h3>
            <LaceBrief schedule={schedule} />
            <LaceBriefApps apps={apps} />
          </section>
          <Separator />
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Apps &amp; accounts</h3>
            <p className="text-xs text-muted-foreground">
              The apps {name} works in. It acts in them only when you approve, and only in the ones switched on here.
            </p>
            <LaceAppsSection laceId={laceId} name={name} apps={apps} />
          </section>
          </fieldset>
          <Separator />
          {/* Any member can confirm it, as in the chat. */}
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Where we operate</h3>
            <LaceJurisdiction name={name} regulations={regulations} />
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
          {role === "owner" && (
            <>
              <Separator />
              <section className="flex flex-col gap-3">
                <h3 className="text-sm font-medium">Manage</h3>
                <LaceManage laceId={laceId} name={name} status={status} onChanged={onChanged} />
              </section>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
