import { useEffect } from "react"
import { Check, Link2, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { InboxPlatform } from "@/lib/api"
import { PLATFORM_LABEL } from "@/lib/platforms"
import { PlatformIcon } from "@/components/platform-icon"

import { useLaceChannels } from "./use-lace-channels"

/** What a Lace speaks for on each platform it reads messages and comments on. */
const LINKED_WHAT: Record<InboxPlatform, string> = { facebook: "Page", instagram: "business account", telegram: "bot" }

/** Pick which of the founder's Pages (or business accounts, or bots) a Lace
 * speaks for: their accounts listed, one click links one. Shown in the chat
 * when the Lace asks, in Messaging, and in its app settings. */
export function LinkAccountCard({ laceId, name, platform, onLinked }: {
  laceId: string
  name: string
  platform: InboxPlatform
  onLinked?: () => void
}) {
  const { channels, choices, loading, error, choose, link } = useLaceChannels(laceId)
  const what = LINKED_WHAT[platform]
  const label = PLATFORM_LABEL[platform]
  const linked = channels.find((c) => c.platform === platform)

  useEffect(() => {
    if (!loading && !linked) void choose(platform)
  }, [loading, linked, choose, platform])

  const pick = async (accountId: string) => {
    if (await link(platform, accountId)) onLinked?.()
  }

  return (
    <Card size="sm" className="gap-2 border-theme/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <PlatformIcon platform={platform} className="size-4" /> Pick the {label} {what} {name} speaks for
        </CardTitle>
        <CardDescription>
          {linked ? `${name} reads and posts as ${linked.account_name}.`
            : `${label} is connected, but ${name} doesn't know which ${what} is yours to work on.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {loading || (!linked && !choices) ? <Loader2 className="size-4 animate-spin text-muted-foreground" /> : null}
        {linked && (
          <p className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
            <Check className="size-4" /> Linked: {linked.account_name}
          </p>
        )}
        {!linked && choices?.platform === platform && (
          choices.accounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">This {label} account manages no {what}.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {choices.accounts.map((account) => (
                <Button key={account.id} size="sm" variant="outline" onClick={() => void pick(account.id)}>
                  <Link2 /> {account.name}
                </Button>
              ))}
            </div>
          )
        )}
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      </CardContent>
    </Card>
  )
}
