import { useCallback, useEffect } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ArrowRight, FileText, Plus } from "lucide-react"

import { Lace } from "@/components/lace-mascot"
import { Button, buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { listAllLaceActivity, type LaceActivityItemDto, type ActivityKind } from "@/lib/api"
import { ensureLacesLoaded, useLaces } from "@/lib/laces-store"
import { cn } from "@/lib/utils"
import { usePageTitle } from "@/lib/use-page-title"

import { sectionHash, type FeedSection, type FeedTarget } from "./lace-activity-actions"
import { ActivityStepper } from "./lace-activity"
import { LacePanelTabs, PanelIntro, type PanelTab } from "./lace-panel-tabs"
import { useActivityPages } from "./use-activity-pages"
import { useSection } from "./use-lace-section"

const MASCOT_PX = 16

type HomeSection = Extract<FeedSection, "activity" | "opportunities" | "competitors">

interface HomeFilter {
  value: HomeSection
  label: string
  /** The activity kind the tab narrows to; none shows everything. */
  kind: ActivityKind | null
  intro: string
  empty: string
}

const HOME_FILTERS: readonly HomeFilter[] = [
  { value: "activity", label: "Activity", kind: null, intro: "What your Laces did and found, a day at a time.",
    empty: "Nothing yet. As your Laces search, draft and hear back, it shows here." },
  { value: "opportunities", label: "Opportunities", kind: "opportunities_found",
    intro: "When your Laces found programmes, grants and events worth a look.",
    empty: "No opportunities found yet." },
  { value: "competitors", label: "Competitor moves", kind: "competitor_moves",
    intro: "What competitors did lately, as your Laces spotted it.",
    empty: "No competitor moves spotted yet." },
]
const HOME_SECTIONS = HOME_FILTERS.map((filter) => filter.value)

function href(laceId: string, { tab, section }: FeedTarget): string {
  return `/lace/${laceId}/${tab}${section ? sectionHash(section) : ""}`
}

/** Home: every Lace's activity at once, a stepper per day, each item tagged
 * with its Lace and opening into it. Opportunities and Competitor moves are
 * the same timeline narrowed to that kind. Which Laces need the founder sits
 * on top. */
export default function LaceHomeFeed() {
  usePageTitle("Home Feed")
  const navigate = useNavigate()
  const { laces, loaded } = useLaces()
  const fetchPage = useCallback((before?: string) => listAllLaceActivity(before), [])
  const feed = useActivityPages<LaceActivityItemDto>(fetchPage)
  const [section, setSection] = useSection<HomeSection>(HOME_SECTIONS)
  const waiting = laces.filter((lace) => lace.mood === "alert")

  useEffect(() => ensureLacesLoaded(), [])

  if (loaded && laces.length === 0) {
    return (
      // Centred in the page, like the create form it leads to.
      <div className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="flex w-full max-w-md flex-col items-center gap-4 text-center">
          <Lace state="idle" size={72} decorative />
          <h1 className="text-xl font-medium">Create your first Lace</h1>
          <p className="text-sm text-muted-foreground">
            Give it your startup's website. It learns what you sell, then works alongside you: spotting opportunities,
            finding customers and partners, watching competitors, and drafting outreach and replies.
          </p>
          <Link to="/new" className={cn(buttonVariants())}><Plus /> New Lace</Link>
        </div>
      </div>
    )
  }

  const timeline = (kind: HomeFilter["kind"], intro: string, empty: string) => {
    const items = kind ? feed.items.filter((item) => item.kind === kind) : feed.items
    return (
      <>
        <PanelIntro>{intro}</PanelIntro>
        {feed.loading ? (
          <div className="flex flex-col gap-3"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ActivityStepper
            items={items}
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
    )
  }
  const unread = (kind: HomeFilter["kind"]) =>
    feed.items.filter((item) => item.read_at === null && (!kind || item.kind === kind)).length
  const tabs: PanelTab<HomeSection>[] = HOME_FILTERS.map((filter) => ({
    value: filter.value, label: filter.label, waiting: unread(filter.kind),
    content: timeline(filter.kind, filter.intro, filter.empty),
  }))

  return (
    // The app shell clips overflow; the page scrolls itself, as a Lace's Feed does.
    <div className="min-h-0 flex-1 overflow-y-auto">
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
        </section>
      } />
    </div>
  )
}
