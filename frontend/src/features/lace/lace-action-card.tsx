import { useState } from "react"
import { Check, ExternalLink, Loader2, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import type { ActionBlockDto } from "@/lib/api"
import { PLATFORM_LABEL } from "@/lib/platforms"

import type { LaceChat } from "./use-lace-chat"

const SAID: Record<string, string> = {
  done: "Done", failed: "Didn’t go through", declined: "Declined", running: "Running", gone: "No longer available",
}

/** Something the Lace proposes doing in one of the founder's apps: what will
 * happen and what it will say, with Approve and Decline. Nothing runs until
 * they approve; then it shows how it went. */
export function ActionCard({ block, chat, onDecided }: {
  block: ActionBlockDto
  chat: LaceChat
  /** Called after the founder decides, for lists outside the chat to refresh. */
  onDecided?: () => Promise<void> | void
}) {
  const [busy, setBusy] = useState<"approve" | "decline" | null>(null)
  const status = block.status ?? "proposed"
  const app = (PLATFORM_LABEL as Record<string, string>)[block.app] ?? block.app
  const decide = async (verdict: "approve" | "decline") => {
    setBusy(verdict)
    await chat.decideAction(block.id, verdict)
    await onDecided?.()
    setBusy(null)
  }

  return (
    <Card size="sm" className="border-theme/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          {block.title}
          {status !== "proposed" && <Badge variant={status === "failed" ? "destructive" : "outline"}>{SAID[status] ?? status}</Badge>}
        </CardTitle>
        {status === "proposed" && (
          <CardDescription>Runs only when you approve it, from your {app} account.</CardDescription>
        )}
      </CardHeader>
      {block.preview && (
        <CardContent>
          <p className="line-clamp-6 rounded-md bg-muted/60 px-3 py-2 text-sm whitespace-pre-wrap">{block.preview}</p>
        </CardContent>
      )}
      {(status === "proposed" || block.result || block.url) && (
        <CardFooter className="flex-wrap gap-2">
          {status === "proposed" ? (
            <>
              <Button size="sm" onClick={() => void decide("approve")} disabled={busy !== null || chat.working}>
                {busy === "approve" ? <Loader2 className="animate-spin" /> : <Check />} Approve
              </Button>
              <Button size="sm" variant="ghost" onClick={() => void decide("decline")} disabled={busy !== null}>
                {busy === "decline" ? <Loader2 className="animate-spin" /> : <X />} Decline
              </Button>
            </>
          ) : (
            <>
              {block.result && <p className={`text-xs ${status === "failed" ? "text-destructive" : "text-muted-foreground"}`}>{block.result}</p>}
              {block.url && (
                <a href={block.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs hover:underline">
                  Open <ExternalLink className="size-3" />
                </a>
              )}
            </>
          )}
        </CardFooter>
      )}
    </Card>
  )
}
