import { Database } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { LaceAccountDto } from "@/lib/api"

import { crmLabel } from "./crm-label"

/** Where a lead stands in the founder's CRM, as a quiet badge beside its name; nothing when it isn't in the CRM. */
export function CrmBadge({ account }: { account: LaceAccountDto }) {
  const label = crmLabel(account)
  if (!label) return null
  return (
    <Badge variant="outline" className="gap-1 font-normal text-muted-foreground">
      <Database aria-hidden className="size-3" />
      {label}
    </Badge>
  )
}
