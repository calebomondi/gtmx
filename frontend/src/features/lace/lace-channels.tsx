import { Link2, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { InboxPlatform } from "@/lib/api"

import { useLaceChannels } from "./use-lace-channels"

const PLATFORMS: { id: InboxPlatform; label: string; what: string; link: string }[] = [
  { id: "instagram", label: "Instagram", what: "business account", link: "Link an Instagram business account" },
  { id: "facebook", label: "Facebook", what: "Page", link: "Link a Facebook Page" },
]

/** Link the founder's Instagram business account or Facebook Page, so the
 * Lace reads the DMs people send it and drafts the answers. */
export function LaceChannels({ laceId }: { laceId: string }) {
  const { channels, choices, loading, error, choose, link, unlink, cancel } = useLaceChannels(laceId)
  if (loading) return <Skeleton className="h-16 w-full" />
  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-muted-foreground">
        When people message your linked accounts, your Lace reads the messages and drafts answers for you to send.
        Connect the account first, under Apps & accounts in this Lace's settings.
      </p>
      {PLATFORMS.map((platform) => {
        const linked = channels.filter((c) => c.platform === platform.id)
        return (
          <section key={platform.id} className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">{platform.label}</h3>
            {linked.map((c) => (
              <div key={c.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                <span>{c.account_name}</span>
                <Button variant="ghost" size="icon" aria-label={`Unlink ${c.account_name}`} onClick={() => void unlink(c.id)}>
                  <Trash2 />
                </Button>
              </div>
            ))}
            {choices?.platform === platform.id ? (
              <div className="flex flex-col gap-1">
                {choices.accounts.length === 0 && (
                  <p className="text-xs text-muted-foreground">Your connection manages no {platform.label} {platform.what}.</p>
                )}
                {choices.accounts.map((a) => (
                  <Button key={a.id} variant="outline" size="sm" className="justify-start"
                          onClick={() => void link(platform.id, a.id)}>
                    Link {a.name}
                  </Button>
                ))}
                <Button variant="ghost" size="sm" className="w-fit" onClick={cancel}>Cancel</Button>
              </div>
            ) : (
              <Button variant="outline" size="sm" className="w-fit" onClick={() => void choose(platform.id)}>
                <Link2 /> {platform.link}
              </Button>
            )}
          </section>
        )
      })}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
  )
}
