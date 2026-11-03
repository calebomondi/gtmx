import { useState } from "react"

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useIsMobile } from "@/hooks/use-mobile"
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
import { SECTIONS, type SettingsSection } from "./settings-sections"

/** A Lace's settings and memory, one section at a time: the sections down
 * the left (across the top on a phone), the chosen one on the right. */
export function LaceSettings({ laceId, name, status, role, facts, apps, regulations, open, initialSection,
                               onOpenChange, onChanged }: {
  laceId: string
  name: string
  status: LaceStatus
  /** The person's role: members see what admins set, without changing it. */
  role: LaceRole
  facts: FactDto[]
  apps: LaceApps
  regulations: LaceRegulations
  open: boolean
  /** Where it opens; the first section otherwise. */
  initialSection?: SettingsSection | null
  onOpenChange: (open: boolean) => void
  /** The Lace was archived or restored. */
  onChanged: () => void
}) {
  const schedule = useLaceBrief(laceId)
  const mobile = useIsMobile()
  const manages = role !== "member"
  const sections = SECTIONS.filter((s) => !s.owner || role === "owner")
  const [current, setCurrent] = useState<SettingsSection>(initialSection ?? "watch")

  const body: Record<SettingsSection, React.ReactNode> = {
    watch: <LaceWatch name={name} schedule={schedule} />,
    brief: <div className="flex flex-col gap-4"><LaceBrief schedule={schedule} /><LaceBriefApps apps={apps} /></div>,
    apps: <LaceAppsSection laceId={laceId} name={name} apps={apps} />,
    where: <LaceJurisdiction name={name} regulations={regulations} />,
    knows: <LaceFacts facts={facts} />,
    documents: <LaceDocuments laceId={laceId} name={name} />,
    manage: <LaceManage laceId={laceId} name={name} status={status} onChanged={onChanged} />,
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[min(42rem,85dvh)] gap-0 p-0 sm:max-w-4xl">
        <Tabs value={current} onValueChange={(value) => setCurrent(value as SettingsSection)}
              orientation={mobile ? "horizontal" : "vertical"} className="min-h-0 flex-1 gap-0 md:flex-row">
          <nav className="flex shrink-0 flex-col gap-3 border-b bg-muted/40 p-4 md:w-56 md:border-r md:border-b-0">
            <div className="pr-8 md:pr-0">
              <DialogTitle>{name}'s settings</DialogTitle>
              <DialogDescription className="sr-only">Choose a section to see and change it.</DialogDescription>
            </div>
            <TabsList variant="line" aria-label="Settings sections"
                      className="-mx-1 max-w-[calc(100%+0.5rem)] justify-start overflow-x-auto px-1 md:mx-0 md:w-full md:max-w-none md:items-stretch md:overflow-visible">
              {sections.map(({ id, label, icon: Icon }) => (
                <TabsTrigger key={id} value={id} className="h-auto flex-none px-2 py-1.5 md:w-full">
                  <Icon /> {label}
                </TabsTrigger>
              ))}
            </TabsList>
          </nav>
          {sections.map((section) => (
            <TabsContent key={section.id} value={section.id} className="min-h-0 overflow-y-auto p-5 md:p-6">
              <header className="mb-5 flex flex-col gap-1 pr-8">
                <h2 className="text-base font-medium">
                  {section.id === "knows" ? `What ${name} knows (${facts.length})` : section.label}
                </h2>
                {section.about && <p className="text-sm text-muted-foreground">{section.about(name)}</p>}
              </header>
              {section.admins && !manages && (
                <p className="mb-4 rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                  Its admins and owner change this. You can see it here.
                </p>
              )}
              {/* A disabled fieldset turns off every control in it, for members. */}
              <fieldset disabled={section.admins && !manages} className="min-w-0">
                {body[section.id]}
              </fieldset>
            </TabsContent>
          ))}
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
