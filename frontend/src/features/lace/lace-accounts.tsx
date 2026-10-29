import { ExternalLink, Loader2, MessageCircle, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { LaceAccountDto } from "@/lib/api"
import { cn } from "@/lib/utils"

import { ITEM_CARD } from "./feed-styles"

type Strength = NonNullable<LaceAccountDto["case"]>["strength"]

const STRENGTH_BARS: Record<Strength, number> = { strong: 3, moderate: 2, weak: 1 }
const CHANNEL_LABELS: Record<string, string> = {
  linkedin: "LinkedIn", instagram: "Instagram", tiktok: "TikTok", facebook: "Facebook", x: "X",
}

/** How strong the fit is, as three bars and a word. */
function FitMeter({ strength }: { strength: Strength }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground" title={`${strength} fit`}>
      <span aria-hidden className="flex items-end gap-0.5">
        {[1, 2, 3].map((bar) => (
          <span key={bar} className={cn("w-1 rounded-sm", bar <= STRENGTH_BARS[strength] ? "bg-theme" : "bg-muted")}
                style={{ height: 4 + bar * 3 }} />
        ))}
      </span>
      <span className="capitalize">{strength} fit</span>
    </span>
  )
}

/** The case for the account, step by step: why now, their need, how we
 * meet it, what it gets them, and how to open. */
function WhyTheyFit({ account }: { account: LaceAccountDto }) {
  const steps = [
    account.trigger && {
      label: "Why now",
      text: account.trigger.event,
      source: account.trigger.source,
    },
    account.case?.need && { label: "Their need", text: account.case.need },
    account.case?.capability && { label: "How we help", text: account.case.capability },
    account.case?.payoff && { label: "Payoff", text: account.case.payoff },
    account.case?.angle && { label: "Opening", text: account.case.angle },
  ].filter(Boolean) as { label: string; text: string; source?: string | null }[]
  if (steps.length === 0) return null
  return (
    <dl className="mt-1 grid grid-cols-[6.5rem_1fr] gap-x-3 gap-y-1.5 rounded-lg bg-muted/40 p-3 text-sm">
      {steps.map((step) => (
        <div key={step.label} className="contents">
          <dt className="text-xs font-medium text-muted-foreground">{step.label}</dt>
          <dd>
            {step.text}
            {step.source && (
              <a href={step.source} target="_blank" rel="noreferrer"
                 className="ml-1.5 inline-flex items-center gap-0.5 text-xs text-muted-foreground hover:underline">
                source <ExternalLink className="size-3" />
              </a>
            )}
          </dd>
        </div>
      ))}
    </dl>
  )
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
          {c.email && <span className="ml-2 text-muted-foreground">{c.email}</span>}
          {c.linkedin && <a href={c.linkedin} target="_blank" rel="noreferrer" className="ml-2 text-muted-foreground hover:underline">LinkedIn</a>}
        </p>
      ))}
      {(emails.length > 0 || channels.length > 0) && (
        <p className="flex flex-wrap gap-x-2 text-muted-foreground">
          {emails.slice(0, 1).map((c) => <span key={c.email}>{c.email}</span>)}
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

/** Leads: who they are, why they fit (the trigger that makes now
 * the moment, their need, how we meet it, the payoff), who to reach, and a
 * way to talk it through with the Lace. Dismissing one drops it for good. */
export function LaceAccounts({ accounts, finding, onDismiss, name, onDiscuss }: {
  accounts: LaceAccountDto[]
  finding: boolean
  onDismiss: (id: string) => void
  name: string
  onDiscuss: (account: LaceAccountDto) => void
}) {
  return (
    <div className="flex flex-col gap-4">
      {finding && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Loader2 className="size-4 animate-spin" /> Looking for accounts or their contacts. This takes several minutes.
        </p>
      )}
      {accounts.length === 0 && !finding && (
        <p className="text-sm text-muted-foreground">None yet. Ask {name} to find leads.</p>
      )}
      <ul className="flex flex-col gap-3">
        {accounts.map((a) => (
          <li key={a.id} className={`${ITEM_CARD} flex items-start justify-between gap-3`}>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="font-medium">{a.name}</span>
                {a.case && <FitMeter strength={a.case.strength} />}
                {a.geo && <span className="text-xs text-muted-foreground">{a.geo}</span>}
              </div>
              {a.website && (
                <a href={a.website} target="_blank" rel="noreferrer"
                   className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:underline">
                  {a.website.replace(/^https?:\/\/(www\.)?/, "")} <ExternalLink className="size-3" />
                </a>
              )}
              <WhyTheyFit account={a} />
              <Reach account={a} />
              <Button size="sm" variant="outline" className="mt-1 w-fit rounded-full border-theme/40 hover:bg-theme/10"
                      onClick={() => onDiscuss(a)}>
                <MessageCircle /> Discuss with {name}
              </Button>
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
