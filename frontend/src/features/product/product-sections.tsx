import type { ReactNode } from 'react'
import { CornerRightDown, Pencil } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * The three layout primitives every sub-tab of the Offer tab is built from.
 *
 * Extracted so `offer-tabs.tsx` can render a panel in the Offer tab's own visual
 * language without importing the 1500-line tab component to borrow a `Row` --
 * which would have been a cycle, and would have pulled the whole tab's state
 * into anything that wanted one card.
 */

export function TagPills({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <span className="text-sm text-muted-foreground italic">—</span>
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-xs text-muted-foreground"
        >
          {item}
        </span>
      ))}
    </div>
  )
}

export function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] inline-flex font-medium tracking-wide text-foreground uppercase">
        <CornerRightDown className="h-3.5 w-3.5" />
        {label}
      </span>
      <div className="text-sm leading-relaxed text-muted-foreground">{value}</div>
    </div>
  )
}

export function SectionCard({
  icon,
  title,
  description,
  onEdit,
  children,
}: {
  icon: ReactNode
  title: string
  description?: string
  onEdit?: () => void
  children: ReactNode
}) {
  return (
    <Card className="">
      <CardHeader className="flex flex-row items-start justify-between gap-2 border-b p-4 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-amber-500">
            {icon}
          </div>
          <div className="min-w-0">
            <CardTitle className="text-sm font-semibold">{title}</CardTitle>
            {description && (
              <CardDescription className="text-xs">{description}</CardDescription>
            )}
          </div>
        </div>
        {onEdit && (
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            aria-label={`Edit ${title}`}
            className="shrink-0 cursor-pointer text-muted-foreground hover:text-foreground"
            onClick={onEdit}
          >
            <Pencil className="size-4" />
          </Button>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3 p-4">{children}</CardContent>
    </Card>
  )
}