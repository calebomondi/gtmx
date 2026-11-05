import { PlatformIcon } from "@/components/platform-icon"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { LaceAppDto, Mailbox } from "@/lib/api"

/** Where a new email goes from, picked on the draft as it's sent: shown with
 * more than one mailbox connected. `value` is the draft's pick, else the one
 * the Lace sends from. */
export function DraftMailbox({ mailboxes, value, disabled, onPick }: {
  mailboxes: LaceAppDto[]
  value: Mailbox | null
  disabled: boolean
  onPick: (mailbox: Mailbox) => void
}) {
  if (mailboxes.length < 2) return null
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted-foreground">From</span>
      <ToggleGroup value={value ? [value] : []} onValueChange={(next) => next[0] && onPick(next[0] as Mailbox)}
                   variant="outline" size="sm" aria-label="Send from" disabled={disabled}>
        {mailboxes.map((m) => (
          <ToggleGroupItem key={m.platform} value={m.platform} title={m.account_name ?? m.label}
                           className="data-[pressed]:border-theme/60 data-[pressed]:bg-theme/15">
            <PlatformIcon platform={m.platform} className="size-3.5" /> {m.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}
