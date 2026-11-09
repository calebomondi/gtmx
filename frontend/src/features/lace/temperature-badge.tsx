import { Flame } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { LeadTemperature } from "@/lib/api"
import { cn } from "@/lib/utils"

import { TEMPERATURE_LABEL } from "./lead-temperature"

const STYLE: Record<LeadTemperature, string> = {
  hot: "border-orange-500/40 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  warm: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  cold: "border-border bg-muted text-muted-foreground",
  customer: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
}

/** A lead's temperature as a small badge: hot, warm, cold or customer;
 * nothing when it isn't known (a contact whose account isn't saved). */
export function TemperatureBadge({ temperature, className }: {
  temperature: LeadTemperature | undefined
  className?: string
}) {
  if (!temperature) return null
  return (
    <Badge variant="outline" className={cn("gap-1 font-medium", STYLE[temperature], className)}>
      {temperature === "hot" && <Flame aria-hidden className="size-3" />}
      {TEMPERATURE_LABEL[temperature]}
    </Badge>
  )
}
