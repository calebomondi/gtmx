import { ExternalLink, Loader2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { LaceAccountDto } from "@/lib/api"

const STRENGTH_VARIANT = { strong: "default", moderate: "secondary", weak: "outline" } as const
const CHANNEL_LABELS: Record<string, string> = {
  linkedin: "LinkedIn", instagram: "Instagram", tiktok: "TikTok", facebook: "Facebook", x: "X",
}

/** Who to reach at the account: named people first, else its own channels. */
function Reach({ account }: { account: LaceAccountDto }) {
  const people = account.contacts.filter((c) => c.name && (c.email || c.linkedin))
  const emails = account.contacts.filter((c) => !c.name && c.email)
  const channels = Object.entries(account.channels)
  if (account.contact_status === "none") {
    return <p className="text-xs text-muted-foreground">No one found to contact yet.</p>
  }
  return (
    <div className="flex flex-col gap-0.5 text-xs">
      {people.slice(0, 2).map((c) => (
        <p key={c.email ?? c.linkedin}>
          <span className="font-medium">{c.name}</span>{c.title && `, ${c.title}`}
          {c.email && <a href={`mailto:${c.email}`} className="ml-2 text-muted-foreground hover:underline">{c.email}</a>}
          {c.linkedin && <a href={c.linkedin} target="_blank" rel="noreferrer" className="ml-2 text-muted-foreground hover:underline">LinkedIn</a>}
        </p>
      ))}
      {(emails.length > 0 || channels.length > 0) && (
        <p className="flex flex-wrap gap-x-2 text-muted-foreground">
          {emails.slice(0, 1).map((c) => <a key={c.email} href={`mailto:${c.email}`} className="hover:underline">{c.email}</a>)}
          {channels.map(([platform, url]) => (
            <a key={platform} href={url} target="_blank" rel="noreferrer" className="hover:underline">
              {CHANNEL_LABELS[platform] ?? platform}
            </a>
          ))}
        </p>
      )}
    </div>
  )
}

/** Target accounts: who they are, the trigger that makes them worth
 * contacting now, and the case for them. Dismissing one drops it for good. */
export function LaceAccounts({ accounts, finding, onDismiss }: {
  accounts: LaceAccountDto[]
  finding: boolean
  onDismiss: (id: string) => void
}) {
  return (
    <div className="flex flex-col gap-4">
      {finding && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Loader2 className="size-4 animate-spin" /> Looking for accounts or their contacts. This takes several minutes.
        </p>
      )}
      {accounts.length === 0 && !finding && (
        <p className="text-sm text-muted-foreground">None yet. Ask your Lace to find customers.</p>
      )}
      <ul className="flex flex-col gap-5">
        {accounts.map((a) => (
          <li key={a.id} className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{a.name}</span>
                {a.case && <Badge variant={STRENGTH_VARIANT[a.case.strength]}>{a.case.strength} fit</Badge>}
                {a.geo && <span className="text-xs text-muted-foreground">{a.geo}</span>}
              </div>
              {a.website && (
                <a href={a.website} target="_blank" rel="noreferrer"
                   className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:underline">
                  {a.website.replace(/^https?:\/\/(www\.)?/, "")} <ExternalLink className="size-3" />
                </a>
              )}
              {a.trigger && (
                <p className="text-sm">
                  <span className="font-medium">Why now: </span>{a.trigger.event}
                  {a.trigger.source && (
                    <a href={a.trigger.source} target="_blank" rel="noreferrer" className="ml-1 text-muted-foreground hover:underline">
                      (source)
                    </a>
                  )}
                </p>
              )}
              {a.case && (
                <p className="text-sm text-muted-foreground">
                  {a.case.need}. {a.case.payoff}.
                </p>
              )}
              <Reach account={a} />
            </div>
            <Button variant="ghost" size="icon" aria-label={`Drop ${a.name}`} title="Not a fit" onClick={() => onDismiss(a.id)}>
              <X />
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}
