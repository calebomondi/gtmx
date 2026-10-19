import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Separator } from "@/components/ui/separator"
import type { FactDto } from "@/lib/api"

import { LaceBrief } from "./lace-brief"
import { LaceFacts } from "./lace-facts"

/** A Lace's settings and memory: when it posts its brief, and everything it
 * knows about the startup, each fact with its source. */
export function LaceSettings({ laceId, name, facts, open, onOpenChange }: {
  laceId: string
  name: string
  facts: FactDto[]
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{name}'s settings</SheetTitle>
          <SheetDescription>Its brief, and what it knows about your startup.</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-6 px-4 pb-6">
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Brief</h3>
            <LaceBrief laceId={laceId} />
          </section>
          <Separator />
          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">What {name} knows ({facts.length})</h3>
            <p className="text-xs text-muted-foreground">Learned from your site, its research and you. Each fact keeps its source.</p>
            <LaceFacts facts={facts} />
          </section>
        </div>
      </SheetContent>
    </Sheet>
  )
}
