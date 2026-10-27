import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { FIND_NOTE_MAX_CHARS, FIND_SUMMARY_MAX_CHARS, type FindDto } from "@/lib/api"

import { FIND_KIND_LABEL, type MyFinds } from "./use-lace-finds"

/** What the description is, per kind, as the reviewer reads it. */
const ABOUT_LABEL = { competitor: "What they do", account: "Why they fit", opportunity: "Why it fits" } as const

/** Rename one of the founder's private finds, reword it, or note it for
 * the reviewer. Open while `find` is set. */
export function FindEditDialog({ find, onClose, finds }: { find: FindDto | null; onClose: () => void; finds: MyFinds }) {
  return (
    <Dialog open={find !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {/* Remounts per find, so the fields start from it. */}
        {find && <EditForm key={`${find.kind}:${find.id}`} find={find} onClose={onClose} finds={finds} />}
      </DialogContent>
    </Dialog>
  )
}

function EditForm({ find, onClose, finds }: { find: FindDto; onClose: () => void; finds: MyFinds }) {
  const [name, setName] = useState(find.name)
  const [summary, setSummary] = useState(find.summary ?? "")
  const [note, setNote] = useState(find.push_note ?? "")
  const [saving, setSaving] = useState(false)
  const save = async () => {
    setSaving(true)
    const saved = await finds.edit(find, { name: name.trim(), summary: summary.trim() || null, note: note.trim() || null })
    setSaving(false)
    if (saved) onClose()
  }
  return (
    <form className="contents" onSubmit={(e) => {
      e.preventDefault()
      void save()
    }}>
      <DialogHeader>
        <DialogTitle>Edit {FIND_KIND_LABEL[find.kind].toLowerCase()}</DialogTitle>
        <DialogDescription>Only you see it until you push it. The note goes to whoever reviews it.</DialogDescription>
      </DialogHeader>
      <FieldGroup className="px-4">
        <Field>
          <FieldLabel htmlFor="find-name">Name</FieldLabel>
          <Input id="find-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={255} required />
        </Field>
        <Field>
          <FieldLabel htmlFor="find-summary">{ABOUT_LABEL[find.kind]}</FieldLabel>
          <Textarea id="find-summary" value={summary} onChange={(e) => setSummary(e.target.value)} rows={3}
                    maxLength={FIND_SUMMARY_MAX_CHARS} />
        </Field>
        <Field>
          <FieldLabel htmlFor="find-note">Note for the reviewer</FieldLabel>
          <Textarea id="find-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2}
                    maxLength={FIND_NOTE_MAX_CHARS} placeholder="Why it's worth it" />
        </Field>
      </FieldGroup>
      <DialogFooter className="sm:flex-row sm:justify-end">
        <DialogClose render={<Button variant="outline" type="button" disabled={saving} />}>Cancel</DialogClose>
        <Button type="submit" disabled={saving || !name.trim()}>{saving ? "Saving…" : "Save"}</Button>
      </DialogFooter>
    </form>
  )
}
