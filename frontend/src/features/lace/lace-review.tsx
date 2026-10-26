import { Bookmark, ExternalLink, X } from "lucide-react"

import { Button } from "@/components/ui/button"

import type { ReviewItem } from "./feed-review"

/** What a search found in one section, waiting for the founder: save it to
 * have the Lace work from it, or dismiss it for good. */
export function LaceReview({ items, saveLabel = "Save", onSave, onDismiss }: {
  items: ReviewItem[]
  saveLabel?: string
  onSave: (id: string) => void
  onDismiss: (id: string) => void
}) {
  if (items.length === 0) return null
  return (
    <section aria-label="To review" className="mb-4 flex flex-col gap-2 rounded-lg border border-dashed border-theme/50 p-3">
      <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">To review ({items.length})</h3>
      <ul className="divide-y">
        {items.map((item) => (
          <li key={item.id} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-start sm:gap-3">
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1 text-sm font-medium">
                {item.title}
                {item.url && (
                  <a href={item.url} target="_blank" rel="noreferrer" aria-label={`Open ${item.title}`}
                     className="text-muted-foreground hover:text-foreground">
                    <ExternalLink className="size-3" />
                  </a>
                )}
              </p>
              {item.detail && <p className="truncate text-xs text-muted-foreground">{item.detail}</p>}
              {item.why && <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{item.why}</p>}
            </div>
            <div className="flex shrink-0 gap-1">
              <Button size="sm" onClick={() => onSave(item.id)}><Bookmark /> {saveLabel}</Button>
              <Button size="sm" variant="ghost" onClick={() => onDismiss(item.id)} aria-label={`Dismiss ${item.title}`}>
                <X /> Dismiss
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
