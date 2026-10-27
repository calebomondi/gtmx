import { useState } from "react"
import { X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { Dismissal, DismissReason } from "@/lib/api"
import { cn } from "@/lib/utils"

const REASONS: readonly { value: DismissReason; label: string }[] = [
  { value: "not_our_buyer", label: "Not our buyer" },
  { value: "too_small", label: "Too small" },
  { value: "wrong_place", label: "Wrong place" },
  { value: "no_need", label: "No need for us" },
  { value: "other", label: "Other" },
]

/** Dismiss, asking why first: the reason teaches later searches what to
 * steer clear of. Skipping it just dismisses. */
export function DismissWithReason({ title, onDismiss }: { title: string; onDismiss: (why?: Dismissal) => void }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState<DismissReason | null>(null)
  const [note, setNote] = useState("")
  const done = (why?: Dismissal) => {
    setOpen(false)
    onDismiss(why)
  }
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button size="sm" variant="ghost" aria-label={`Dismiss ${title}`} />}>
        <X /> Dismiss
      </PopoverTrigger>
      <PopoverContent align="end" className="flex w-72 flex-col gap-2.5 text-sm">
        <p className="font-medium">Why isn't {title} a fit?</p>
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Reason">
          {REASONS.map((r) => (
            <button key={r.value} type="button" role="radio" aria-checked={reason === r.value}
                    onClick={() => setReason(r.value)}
                    className={cn("cursor-pointer rounded-full border px-2.5 py-1 text-xs transition-colors hover:border-theme/60",
                                  reason === r.value && "border-theme bg-theme/15")}>
              {r.label}
            </button>
          ))}
        </div>
        <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} className="h-8 text-xs"
               placeholder="A few words more (optional)" aria-label="More about why" />
        <p className="text-xs text-muted-foreground">Later searches will steer clear of the like.</p>
        <div className="flex justify-end gap-1.5">
          <Button size="xs" variant="ghost" onClick={() => done()}>Just dismiss</Button>
          <Button size="xs" disabled={!reason} onClick={() => reason && done({ reason, note: note.trim() || undefined })}>
            Dismiss
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
