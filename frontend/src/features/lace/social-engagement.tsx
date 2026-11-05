import { Check, ExternalLink, MessageCircleQuestion, Sparkles, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import type { SocialItemDto } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"

import { askAbout, HEARD_SECTIONS } from "./social-model"
import type { LaceSocial } from "./use-lace-social"

function HeardCard({ item, name, social, discuss }: {
  item: SocialItemDto
  name: string
  social: LaceSocial
  discuss: (prompt: string) => void
}) {
  const when = item.said_at ?? item.heard_at
  return (
    <Card size="sm" className="gap-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          @{item.author ?? "someone"}
          <span className="text-xs font-normal text-muted-foreground">{formatRelativeTime(Date.parse(when))}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5 text-sm">
        <p className="whitespace-pre-line">{item.text}</p>
        {item.note && <p className="text-xs text-muted-foreground"><Sparkles className="mr-1 inline size-3 text-theme" />{item.note}</p>}
      </CardContent>
      <CardFooter className="flex-wrap gap-2">
        <Button size="sm" onClick={() => discuss(askAbout(item))}>
          <MessageCircleQuestion /> Ask {name}
        </Button>
        {item.url && (
          <a href={item.url} target="_blank" rel="noreferrer" className={buttonVariants({ size: "sm", variant: "ghost" })}>
            <ExternalLink /> Open
          </a>
        )}
        <Button size="sm" variant="ghost" onClick={() => void social.setStatus(item.id, "done")}><Check /> Done</Button>
        <Button size="sm" variant="ghost" onClick={() => void social.setStatus(item.id, "dismissed")}><X /> Dismiss</Button>
      </CardFooter>
    </Card>
  )
}

/** What people said to or about the founder on one platform, as their Lace
 * sorted it: leads and questions first. Each can go to the Lace (it drafts a
 * reply or works out who someone is), or be marked done or set aside. */
export function SocialEngagement({ items, name, social, discuss }: {
  items: SocialItemDto[]
  name: string
  social: LaceSocial
  discuss: (prompt: string) => void
}) {
  const open = items.filter((i) => i.status === "new")
  const handled = items.length - open.length
  if (open.length === 0) {
    return (
      <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
        Nothing waiting. {name} listens once a day and sorts new comments and mentions here: leads, questions,
        feedback and praise.{handled ? ` ${handled} already handled.` : ""}
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-5">
      {HEARD_SECTIONS.map(({ kind, title }) => {
        const shown = open.filter((i) => i.verdict === kind)
        if (shown.length === 0) return null
        return (
          <section key={kind} className="flex flex-col gap-2">
            <h3 className="flex items-center gap-2 text-sm font-medium">{title} <Badge variant="secondary">{shown.length}</Badge></h3>
            <div className="grid gap-2 sm:grid-cols-2">
              {shown.map((item) => <HeardCard key={item.id} item={item} name={name} social={social} discuss={discuss} />)}
            </div>
          </section>
        )
      })}
    </div>
  )
}
