import type { ReactNode } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ArrowRight, ExternalLink, MessageCircle } from "lucide-react"

import { Lace } from "@/components/lace-mascot"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { LaceTagDto } from "@/lib/api"

import { sectionHash, type FeedSection } from "./lace-activity-actions"
import type { DiscussState } from "./discuss"
import { ITEM_CARD } from "./feed-styles"

const MASCOT_PX = 16

/** One saved item on Home: whose it is, what it is, and the way into its
 * Lace (to its Feed tab, or the chat with the item to discuss). */
export function HomeItem({ tag, section, discuss, children }: {
  tag: LaceTagDto
  section: FeedSection
  discuss: string
  children: ReactNode
}) {
  const navigate = useNavigate()
  return (
    <li className={`${ITEM_CARD} flex flex-col gap-1.5`}>
      <Link to={`/lace/${tag.lace_id}`} className="inline-flex w-fit items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
        <Lace state="idle" size={MASCOT_PX} animated={false} decorative /> {tag.lace_name}
      </Link>
      {children}
      <div className="mt-1 flex flex-wrap gap-2">
        <Button size="xs" variant="outline" className="rounded-full border-theme/40 hover:bg-theme/10"
                onClick={() => navigate(`/lace/${tag.lace_id}/chat`, { state: { prefill: discuss } satisfies DiscussState })}>
          <MessageCircle /> Discuss with {tag.lace_name}
        </Button>
        <Button size="xs" variant="ghost" onClick={() => navigate(`/lace/${tag.lace_id}/feed${sectionHash(section)}`)}>
          Open in {tag.lace_name} <ArrowRight />
        </Button>
      </div>
    </li>
  )
}

/** A Home tab's list, its loading and empty states, and a note of what waits
 * for review in the Laces. */
export function HomeList({ loading, empty, toReview, noun, children }: {
  loading: boolean
  empty: boolean
  toReview: number
  noun: string
  children: ReactNode
}) {
  if (loading) return <div className="flex flex-col gap-3"><Skeleton className="h-24 w-full" /><Skeleton className="h-24 w-full" /></div>
  return (
    <div className="flex flex-col gap-3">
      {toReview > 0 && (
        <p className="w-fit rounded-full border border-theme/40 bg-theme/10 px-3 py-1 text-xs">
          {toReview} {toReview === 1 ? `${noun} waits` : `${noun}s wait`} for review in your Laces
        </p>
      )}
      {empty ? <p className="text-sm text-muted-foreground">None saved yet across your Laces.</p>
        : <ul className="flex flex-col gap-3">{children}</ul>}
    </div>
  )
}

export function SiteLink({ url }: { url: string }) {
  return (
    <a href={url} target="_blank" rel="noreferrer" className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:underline">
      {url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")} <ExternalLink className="size-3" />
    </a>
  )
}
