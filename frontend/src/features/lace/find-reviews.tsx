import { useState } from "react"
import { Check, ExternalLink, Quote, Undo2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import type { FindDto } from "@/lib/api"

import { PersonAvatar } from "./person-avatar"
import { FIND_KIND_LABEL, type FindReviews } from "./use-lace-finds"

/** On the Feed: finds teammates pushed from their private chats, for
 * someone else to approve (the team saves it) or send back with a note. */
export function FindReviewsCard({ reviews }: { reviews: FindReviews }) {
  const items = reviews.items ?? []
  if (items.length === 0) return null
  return (
    <Card className="mb-4 ring-theme/30">
      <CardHeader>
        <CardTitle>To review</CardTitle>
        <CardDescription>Found in a teammate's private chat. Approve to save it for the team.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col divide-y">
          {items.map((find) => <ReviewRow key={`${find.kind}:${find.id}`} find={find} reviews={reviews} />)}
        </ul>
      </CardContent>
    </Card>
  )
}

function ReviewRow({ find, reviews }: { find: FindDto; reviews: FindReviews }) {
  // Sending back asks why first.
  const [noting, setNoting] = useState(false)
  const [note, setNote] = useState("")
  const [busy, setBusy] = useState(false)
  const act = async (run: () => Promise<void>) => {
    setBusy(true)
    await run()
    setBusy(false)
  }
  const who = find.owner?.name ?? "A teammate"
  return (
    <li className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-sm font-medium">
            <span className="truncate">{find.name}</span>
            <Badge variant="outline" className="shrink-0 text-[10px]">{FIND_KIND_LABEL[find.kind]}</Badge>
          </p>
          {find.summary && <p className="mt-0.5 line-clamp-3 text-xs text-muted-foreground">{find.summary}</p>}
          {find.link ? (
            <a href={find.link} target="_blank" rel="noreferrer"
               className="mt-0.5 flex w-fit max-w-full items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <span className="truncate">{find.detail ?? find.link}</span> <ExternalLink className="size-3 shrink-0" />
            </a>
          ) : find.detail && <p className="truncate text-xs text-muted-foreground">{find.detail}</p>}
          {find.push_note && (
            <p className="mt-1.5 flex items-start gap-1.5 rounded-md bg-muted/60 px-2 py-1 text-xs">
              <Quote className="mt-0.5 size-3 shrink-0 text-theme" /> {find.push_note}
            </p>
          )}
          <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            <PersonAvatar name={find.owner?.name ?? null} email={null} avatarUrl={find.owner?.avatar_url ?? null} size="sm"
                          className="size-4" />
            {who}
          </p>
        </div>
        {find.can_review ? (
          <div className="flex shrink-0 gap-1.5">
            <Button size="xs" variant="outline" disabled={busy} onClick={() => setNoting(!noting)}><Undo2 /> Send back</Button>
            <Button size="xs" disabled={busy} onClick={() => void act(() => reviews.approve(find))}><Check /> Approve</Button>
          </div>
        ) : (
          <span className="shrink-0 text-xs text-muted-foreground">Waiting for a teammate</span>
        )}
      </div>
      {noting && (
        <form className="flex gap-1.5" onSubmit={(e) => {
          e.preventDefault()
          void act(() => reviews.sendBack(find, note))
        }}>
          <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} autoFocus
                 placeholder={`Why, for ${who}`} aria-label="Why it goes back" className="h-8 text-sm" />
          <Button size="sm" variant="outline" type="submit" disabled={busy}>Send back</Button>
        </form>
      )}
    </li>
  )
}
