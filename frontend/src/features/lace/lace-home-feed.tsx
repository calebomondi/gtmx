import { useCallback, useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Activity, ArrowRight, Building2, FileText, Plus, Sparkles, Swords } from "lucide-react"

import { Lace } from "@/components/lace-mascot"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { listAllLaceActivity, type LaceActivityItemDto } from "@/lib/api"
import { ensureLacesLoaded, useLaces } from "@/lib/laces-store"
import { cn } from "@/lib/utils"

import { discussAccount, discussCompetitor, discussOpportunity } from "./discuss"
import { HomeItem, HomeList, SiteLink } from "./home-saved"
import { FEED_SECTIONS, sectionHash, type FeedSection, type FeedTarget } from "./lace-activity-actions"
import { ActivityStepper } from "./lace-activity"
import { LacePanelTabs, PanelIntro, type PanelTab } from "./lace-panel-tabs"
import { useActivityPages } from "./use-activity-pages"
import { useSavedAcrossLaces } from "./use-saved-across-laces"
import { useSection } from "./use-lace-section"

const MASCOT_PX = 16

function href(laceId: string, { tab, section }: FeedTarget): string {
  return `/lace/${laceId}/${tab}${section ? sectionHash(section) : ""}`
}

/** Home: every Lace at once, in the same tabs as a Lace's Feed. Activity
 * (a stepper per day), then the opportunities, customers and competitors
 * each Lace saved, each item tagged with its Lace and opening into it. Which
 * Laces need the founder sits on top. */
export default function LaceHomeFeed() {
  const navigate = useNavigate()
  const { laces, loaded } = useLaces()
  const fetchPage = useCallback((before?: string) => listAllLaceActivity(before), [])
  const feed = useActivityPages<LaceActivityItemDto>(fetchPage)
  const { saved, error } = useSavedAcrossLaces(feed.items[0]?.id ?? "")
  const [section, setSection] = useSection<FeedSection>(FEED_SECTIONS)
  const waiting = laces.filter((lace) => lace.mood === "alert")

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

  const unread = feed.items.filter((item) => item.read_at === null).length
  const tabs: PanelTab<FeedSection>[] = [
    {
      value: "activity", label: "Activity", icon: Activity, waiting: unread,
      content: (
        <>
          <PanelIntro>What your Laces did and found, a day at a time.</PanelIntro>
          {feed.loading ? (
            <div className="flex flex-col gap-3"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
          ) : feed.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing yet. As your Laces search, draft and hear back, it shows here.</p>
          ) : (
            <ActivityStepper
              items={feed.items}
              isFresh={(item) => item.read_at === null}
              onOpen={(item, target) => navigate(href(item.lace_id, target))}
              tag={(item) => (
                <Link to={`/lace/${item.lace_id}`} className="mb-0.5 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
                  <Lace state="idle" size={MASCOT_PX} animated={false} decorative /> {item.lace_name}
                </Link>
              )}
            />
          )}
          {feed.hasMore && feed.items.length > 0 && (
            <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={() => void feed.loadMore()}>
              <FileText /> Older activity
            </Button>
          )}
          {feed.error && <p className="mt-2 text-sm text-destructive" role="alert">{feed.error}</p>}
        </>
      ),
    },
    {
      value: "opportunities", label: "Opportunities", icon: Sparkles, count: saved?.opportunities.length,
      waiting: saved?.to_review.opportunities,
      content: (
        <HomeList loading={!saved && !error} empty={!saved?.opportunities.length} toReview={saved?.to_review.opportunities ?? 0}
                  noun="opportunity">
          {saved?.opportunities.map((o) => (
            <HomeItem key={o.id} tag={o} section="opportunities" discuss={discussOpportunity(o)}>
              <a href={o.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{o.title}</a>
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="secondary" className="capitalize">{o.kind}</Badge>
                {o.organiser && <span>{o.organiser}</span>}
                {o.deadline && <span>closes {o.deadline}</span>}
              </div>
              <p className="text-sm text-muted-foreground">{o.why_it_fits}</p>
            </HomeItem>
          ))}
        </HomeList>
      ),
    },
    {
      value: "accounts", label: "Customers", icon: Building2, count: saved?.accounts.length,
      waiting: saved?.to_review.accounts,
      content: (
        <HomeList loading={!saved && !error} empty={!saved?.accounts.length} toReview={saved?.to_review.accounts ?? 0}
                  noun="customer">
          {saved?.accounts.map((a) => (
            <HomeItem key={a.id} tag={a} section="accounts" discuss={discussAccount(a)}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{a.name}</span>
                {a.case && <Badge variant="secondary" className="capitalize">{a.case.strength} fit</Badge>}
                {a.geo && <span className="text-xs text-muted-foreground">{a.geo}</span>}
              </div>
              {a.trigger && <p className="text-sm"><span className="text-muted-foreground">Why now: </span>{a.trigger.event}</p>}
              {a.case && (
                <p className="text-sm"><span className="text-muted-foreground">How we help: </span>{a.case.capability}</p>
              )}
            </HomeItem>
          ))}
        </HomeList>
      ),
    },
    {
      value: "competitors", label: "Competitors", icon: Swords, count: saved?.competitors.length,
      waiting: saved?.to_review.competitors,
      content: (
        <HomeList loading={!saved && !error} empty={!saved?.competitors.length} toReview={saved?.to_review.competitors ?? 0}
                  noun="competitor">
          {saved?.competitors.map((c) => (
            <HomeItem key={c.id} tag={c} section="competitors" discuss={discussCompetitor(c)}>
              <span className="font-medium">{c.name}</span>
              <SiteLink url={c.website} />
              {c.summary && <p className="line-clamp-2 text-sm text-muted-foreground">{c.summary}</p>}
            </HomeItem>
          ))}
        </HomeList>
      ),
    },
  ]

  return (
    <LacePanelTabs label="Home" tabs={tabs} value={section} onChange={setSection} header={
      <section aria-label="Home" className="flex flex-col gap-3 rounded-2xl border bg-gradient-to-br from-theme/12 via-card to-card p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <h1 className="text-base font-medium">Home</h1>
          <p className="text-xs text-muted-foreground">
            {laces.length} {laces.length === 1 ? "Lace" : "Laces"} at work{waiting.length ? ` · ${waiting.length} need you` : ""}
          </p>
        </div>
        {waiting.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {waiting.map((lace) => (
              <Button key={lace.id} size="sm" variant="outline" className="rounded-full border-theme/40 bg-background/70"
                      onClick={() => navigate(`/lace/${lace.id}/feed`)}>
                <Lace state="alert" size={MASCOT_PX} decorative /> {lace.name} needs you <ArrowRight />
              </Button>
            ))}
          </div>
        )}
        {error && <p className="text-xs text-destructive" role="alert">Couldn't load what your Laces saved: {error}</p>}
      </section>
    } />
  )
}
