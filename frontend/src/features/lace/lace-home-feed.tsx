import { useCallback, useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ArrowRight, FileText, Plus } from "lucide-react"

import { Lace } from "@/components/lace-mascot"
import { Button, buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { listAllLaceActivity, type LaceActivityItemDto } from "@/lib/api"
import { ensureLacesLoaded, useLaces } from "@/lib/laces-store"
import { cn } from "@/lib/utils"

import { sectionHash, type FeedTarget } from "./lace-activity-actions"
import { ActivityRow } from "./lace-activity"
import { LaceSection } from "./lace-section"
import { useActivityPages } from "./use-activity-pages"
import { useOpenedItems } from "./viewer-memory"

const MASCOT_PX = 16

function href(laceId: string, { tab, section }: FeedTarget): string {
  return `/lace/${laceId}/${tab}${section ? sectionHash(section) : ""}`
}

/** Home: what every Lace did and found, newest first, and which of them
 * need the founder. Each item opens in its own Lace. */
export default function LaceHomeFeed() {
  const navigate = useNavigate()
  const { laces, loaded } = useLaces()
  const fetchPage = useCallback((before?: string) => listAllLaceActivity(before), [])
  const feed = useActivityPages<LaceActivityItemDto>(fetchPage)
  const waiting = laces.filter((lace) => lace.mood === "alert")
  const [opened, markOpened] = useOpenedItems("activity")

  useEffect(() => ensureLacesLoaded(), [])

  if (loaded && laces.length === 0) {
    return (
      // Centred in the page, like the create form it leads to.
      <div className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="flex w-full max-w-md flex-col items-center gap-4 text-center">
          <Lace state="idle" size={72} decorative />
          <h1 className="text-xl font-medium">Meet your first Lace</h1>
          <p className="text-sm text-muted-foreground">
            Give it your startup's website. It learns what you sell, then finds your customers and helps you reach them.
          </p>
          <Link to="/new" className={cn(buttonVariants())}><Plus /> New Lace</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      <h1 className="text-xl font-medium">Home</h1>
      {waiting.length > 0 && (
        <section aria-label="Needs you" className="flex flex-wrap items-center gap-2 rounded-xl border border-theme/40 bg-theme/10 p-3">
          <span className="text-sm font-medium">Needs you</span>
          {waiting.map((lace) => (
            <Button key={lace.id} size="sm" variant="outline" onClick={() => navigate(`/lace/${lace.id}/feed`)}>
              <Lace state="alert" size={MASCOT_PX} decorative /> {lace.name} <ArrowRight />
            </Button>
          ))}
        </section>
      )}
      <LaceSection title="Activity" description="What your Laces did and found, newest first.">
        {feed.loading ? (
          <div className="flex flex-col gap-3"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
        ) : feed.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing yet. As your Laces search, draft and hear back, it shows here.</p>
        ) : (
          <ul className="divide-y">
            {feed.items.map((item) => (
              <ActivityRow
                key={item.id}
                item={item}
                fresh={item.read_at === null}
                opened={opened.has(item.id)}
                onOpen={(target) => {
                  markOpened(item.id)
                  navigate(href(item.lace_id, target))
                }}
                lace={
                  <Link to={`/lace/${item.lace_id}`} className="mb-0.5 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
                    <Lace state="idle" size={MASCOT_PX} animated={false} decorative /> {item.lace_name}
                  </Link>
                }
              />
            ))}
          </ul>
        )}
        {feed.hasMore && feed.items.length > 0 && (
          <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={() => void feed.loadMore()}>
            <FileText /> Older activity
          </Button>
        )}
        {feed.error && <p className="mt-2 text-sm text-destructive" role="alert">{feed.error}</p>}
      </LaceSection>
    </div>
  )
}
