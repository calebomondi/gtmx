import { useState } from "react"
import { ListChecks, Loader2, Pencil, Trash2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { INSTRUCTION_CHARS, INSTRUCTION_SCOPES, type InstructionScope, type LaceInstructionDto } from "@/lib/api"

import { useLaceInstructions } from "./use-lace-instructions"

const SCOPE_LABELS: Record<InstructionScope, string> = {
  everything: "Everything",
  competitors: "Competitors",
  leads: "Leads",
  opportunities: "Opportunities",
  outreach: "Emails & replies",
}

/** Writing or rewriting one instruction: its words and what it governs. */
function InstructionForm({ initial, scope: initialScope, busy, submit, cancel, action }: {
  initial: string
  scope: InstructionScope
  busy: boolean
  submit: (text: string, scope: InstructionScope) => Promise<boolean>
  cancel?: () => void
  action: string
}) {
  const [text, setText] = useState(initial)
  const [scope, setScope] = useState<InstructionScope>(initialScope)
  const save = async () => {
    if (await submit(text.trim(), scope) && !cancel) setText("")
  }
  return (
    <div className="flex flex-col gap-2">
      <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={INSTRUCTION_CHARS}
                placeholder="e.g. Only look at competitors selling in Kenya" aria-label="Instruction" />
      <ToggleGroup value={[scope]} onValueChange={(next) => next[0] && setScope(next[0] as InstructionScope)}
                   variant="outline" size="sm" className="flex-wrap" aria-label="Applies to">
        {INSTRUCTION_SCOPES.map((s) => (
          <ToggleGroupItem key={s} value={s}>{SCOPE_LABELS[s]}</ToggleGroupItem>
        ))}
      </ToggleGroup>
      <div className="flex gap-2">
        <Button size="sm" onClick={() => void save()} disabled={busy || !text.trim()}>
          {busy && <Loader2 className="animate-spin" />}{action}
        </Button>
        {cancel && <Button size="sm" variant="ghost" onClick={cancel} disabled={busy}>Cancel</Button>}
      </div>
    </div>
  )
}

function InstructionRow({ item, busy, idle, onEdit, onRemove }: {
  item: LaceInstructionDto
  busy: boolean
  idle: boolean
  onEdit: () => void
  onRemove: () => void
}) {
  return (
    <li className="flex items-start gap-3 rounded-lg border px-3 py-2">
      <ListChecks className="mt-0.5 size-4 shrink-0 text-theme" />
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="text-sm">{item.text}</span>
        <Badge variant="secondary" className="w-fit">{SCOPE_LABELS[item.applies_to]}</Badge>
      </span>
      <Button size="icon-sm" variant="ghost" onClick={onEdit} disabled={!idle} aria-label={`Edit: ${item.text}`}>
        <Pencil />
      </Button>
      <Button size="icon-sm" variant="ghost" onClick={onRemove} disabled={!idle} aria-label={`Remove: ${item.text}`}>
        {busy ? <Loader2 className="animate-spin" /> : <Trash2 />}
      </Button>
    </li>
  )
}

/** How the team wants its Lace to work: kept when said in the chat or added
 * here, followed in every chat and by the searches each one applies to. */
export function LaceInstructions({ laceId, name }: { laceId: string; name: string }) {
  const { items, error, busy, add, edit, remove } = useLaceInstructions(laceId)
  const [editing, setEditing] = useState<string | null>(null)
  const saveEdit = (id: string) => async (text: string, scope: InstructionScope) => {
    const saved = await edit(id, text, scope)
    if (saved) setEditing(null)
    return saved
  }

  if (items === null && !error) return <Skeleton className="h-10 w-full" />
  return (
    <div className="flex flex-col gap-3">
      {items?.length === 0 && (
        <p className="text-sm text-muted-foreground">
          None yet. Tell {name} how to work in the chat, like "skip events outside Africa", and it keeps it here.
        </p>
      )}
      <ul className="flex flex-col gap-1.5">
        {items?.map((item) => editing === item.id ? (
          <li key={item.id} className="rounded-lg border px-3 py-2">
            <InstructionForm initial={item.text} scope={item.applies_to} busy={busy === item.id} action="Save"
                             cancel={() => setEditing(null)} submit={saveEdit(item.id)} />
          </li>
        ) : (
          <InstructionRow key={item.id} item={item} busy={busy === item.id} idle={busy === null && editing === null}
                          onEdit={() => setEditing(item.id)} onRemove={() => void remove(item.id)} />
        ))}
      </ul>
      <InstructionForm initial="" scope="everything" busy={busy === "new"} action="Add instruction" submit={add} />
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
  )
}
