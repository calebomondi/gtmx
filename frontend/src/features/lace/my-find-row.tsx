import { useState } from "react"
import { Clock, ExternalLink, MessageSquarePlus, Pencil, Quote, Trash2, Undo2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { FIND_NOTE_MAX_CHARS, type FindDto } from "@/lib/api"

import type { MyFinds } from "./use-lace-finds"

/** One of the founder's private finds: what it is, its link and their note
 * for the reviewer, with ways to note, edit or remove it while it is theirs. */
export function MyFindRow({ find, ticked, onToggle, finds, onEdit }: {
  find: FindDto
  ticked: boolean
  onToggle: () => void
  finds: MyFinds
  onEdit: () => void
}) {
  const waiting = Boolean(find.proposed_at)
  const [noting, setNoting] = useState(false)
  return (
    <li className="flex items-start gap-2 py-2">
      <Checkbox checked={!waiting && ticked} disabled={waiting} onCheckedChange={onToggle} aria-label={`Push ${find.name}`}
                className="mt-0.5" />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <p className="flex items-center gap-1.5 text-sm">
          <span className="truncate font-medium">{find.name}</span>
          {find.link && (
            <a href={find.link} target="_blank" rel="noreferrer" aria-label={`Open ${find.name}`}
               className="shrink-0 text-muted-foreground hover:text-foreground">
              <ExternalLink className="size-3" />
            </a>
          )}
        </p>
        {find.summary && <p className="line-clamp-2 text-xs text-muted-foreground">{find.summary}</p>}
        {waiting && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground"><Clock className="size-3" /> Waiting for the team</p>
        )}
        {!waiting && find.review_note && (
          <p className="flex items-start gap-1 text-xs text-muted-foreground">
            <Undo2 className="mt-0.5 size-3 shrink-0" /> Sent back: {find.review_note}
          </p>
        )}
        {noting ? (
          <NoteForm find={find} finds={finds} onDone={() => setNoting(false)} />
        ) : find.push_note && (
          <button type="button" disabled={waiting} onClick={() => setNoting(true)}
                  className="flex cursor-pointer items-start gap-1 text-left text-xs text-foreground/80 disabled:cursor-default">
            <Quote className="mt-0.5 size-3 shrink-0 text-theme" /> {find.push_note}
          </button>
        )}
      </div>
      {!waiting && (
        <div className="flex shrink-0 gap-0.5">
          {!find.push_note && !noting && (
            <Action label="Add a note for the reviewer" onClick={() => setNoting(true)}><MessageSquarePlus /></Action>
          )}
          <Action label={`Edit ${find.name}`} onClick={onEdit}><Pencil /></Action>
          <RemoveButton find={find} finds={finds} />
        </div>
      )}
    </li>
  )
}

function Action({ label, onClick, children }: { label: string; onClick?: () => void; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger render={<Button size="icon-xs" variant="ghost" aria-label={label} onClick={onClick} />}>
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

/** The note a reviewer reads with the push. Blank clears it. */
function NoteForm({ find, finds, onDone }: { find: FindDto; finds: MyFinds; onDone: () => void }) {
  const [note, setNote] = useState(find.push_note ?? "")
  const [saving, setSaving] = useState(false)
  return (
    <form className="mt-1 flex gap-1.5" onSubmit={async (e) => {
      e.preventDefault()
      setSaving(true)
      const saved = await finds.edit(find, { note: note.trim() || null })
      setSaving(false)
      if (saved) onDone()
    }}>
      <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={FIND_NOTE_MAX_CHARS} autoFocus
             placeholder="Why it's worth it, for whoever reviews it" aria-label={`Note on ${find.name}`}
             className="h-7 text-xs" onKeyDown={(e) => e.key === "Escape" && onDone()} />
      <Button size="xs" type="submit" disabled={saving}>Save</Button>
      <Button size="xs" variant="ghost" type="button" onClick={onDone}>Cancel</Button>
    </form>
  )
}

/** Remove asks once, in place: there is no undo. */
function RemoveButton({ find, finds }: { find: FindDto; finds: MyFinds }) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button size="icon-xs" variant="ghost" aria-label={`Remove ${find.name}`} />}>
        <Trash2 />
      </PopoverTrigger>
      <PopoverContent align="end" className="flex w-64 flex-col gap-2 text-sm">
        <p>Remove <span className="font-medium">{find.name}</span>? Your chat won't suggest it again.</p>
        <div className="flex justify-end gap-1.5">
          <Button size="xs" variant="ghost" onClick={() => setOpen(false)}>Keep</Button>
          <Button size="xs" variant="destructive" onClick={() => {
            setOpen(false)
            void finds.remove(find)
          }}>Remove</Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
