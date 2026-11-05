import { PlatformIcon } from "@/components/platform-icon"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { LaceAppDto, Mailbox } from "@/lib/api"

/** With more than one mailbox connected: which one new email goes from, and
 * (for the Lace's owner and admins) the choice. Answers always go from the
 * mailbox their conversation is in. */
export function SendFrom({ mailboxes, name, canChoose, onPick }: {
  mailboxes: LaceAppDto[]
  name: string
  canChoose: boolean
  onPick: (mailbox: Mailbox) => void
}) {
  const live = mailboxes.filter((m) => m.connected)
  if (live.length < 2) return null
  const sender = live.find((m) => m.sends_email)
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
      <span className="text-xs text-muted-foreground">New email goes from</span>
      {canChoose ? (
        <ToggleGroup value={sender ? [sender.platform] : []} onValueChange={(next) => next[0] && onPick(next[0] as Mailbox)}
                     variant="outline" size="sm" aria-label="Send new email from">
          {live.map((m) => (
            <ToggleGroupItem key={m.platform} value={m.platform} title={m.account_name ?? m.label}
                             className="data-[pressed]:border-theme/60 data-[pressed]:bg-theme/15">
              <PlatformIcon platform={m.platform} className="size-3.5" /> {m.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      ) : (
        <span className="flex items-center gap-1.5 text-xs font-medium">
          {sender ? <><PlatformIcon platform={sender.platform} className="size-3.5" /> {sender.label}</> : "no mailbox yet"}
        </span>
      )}
      <span className="basis-full text-xs text-muted-foreground">
        {sender
          ? `${name} answers each conversation from the mailbox it's in.`
          : `The mailbox you picked isn't connected or is switched off for ${name}: pick one to send new email.`}
      </span>
    </div>
  )
}
