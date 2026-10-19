import { useNavigate, useParams, useSearchParams } from "react-router-dom"
import { AlertTriangle } from "lucide-react"

import { Lace } from "@/components/lace-mascot"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"

import { LaceFactReview } from "./lace-fact-review"
import { LacePrint } from "./lace-print"
import { useLaceSetup } from "./use-lace-setup"

const PRINT_PX = 128

/** A new Lace being made: printed as it reads the site, then the founder
 * checks what it learned before meeting it. Keyed on the Lace id. */
export default function LaceSetupPage() {
  // The route only renders this page with a lace_id.
  const { lace_id: laceId = "" } = useParams()
  const [params] = useSearchParams()
  return <LaceSetup key={laceId} laceId={laceId} runId={params.get("run")} />
}

function LaceSetup({ laceId, runId }: { laceId: string; runId: string | null }) {
  const navigate = useNavigate()
  const setup = useLaceSetup(laceId, runId)
  const name = setup.lace?.name ?? "your Lace"
  const startup = setup.lace?.startup_name ?? "your startup"
  const meet = () => navigate(`/lace/${laceId}`)

  if (setup.phase === "printing" || setup.phase === "waking") {
    const awake = setup.phase === "waking"
    return (
      <Shell>
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="justify-items-center gap-3 text-center">
            <LacePrint progress={setup.progress} awake={awake} size={PRINT_PX} className="my-4" />
            <CardTitle className="text-xl">{awake ? `${name} is ready` : `Building ${name}`}</CardTitle>
            <CardDescription aria-live="polite">
              {awake ? "Let's check what it learned." : `${setup.step}…`}
            </CardDescription>
            <p className="text-xs text-muted-foreground tabular-nums">{Math.round(setup.progress * 100)}%</p>
          </CardHeader>
        </Card>
      </Shell>
    )
  }

  if (setup.phase === "unreadable") {
    return (
      <Shell>
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="justify-items-center gap-3 text-center">
            <Lace state="idle" size={72} decorative />
            <CardTitle className="text-xl">{name} couldn't read your site</CardTitle>
            <CardDescription className="text-balance">
              Tell {name} what you sell, to whom and at what price, and it will take it from there.
            </CardDescription>
          </CardHeader>
          <CardFooter><Button className="w-full" onClick={meet}>Tell {name}</Button></CardFooter>
        </Card>
      </Shell>
    )
  }

  if (setup.phase === "failed") {
    return (
      <Shell>
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="justify-items-center gap-3 text-center">
            <AlertTriangle className="size-8 text-destructive" />
            <CardTitle className="text-xl">{name} stopped before it finished</CardTitle>
            <CardDescription>{setup.error}</CardDescription>
          </CardHeader>
          <CardFooter className="gap-2">
            <Button variant="outline" className="flex-1" onClick={() => navigate("/new")}>Start again</Button>
            <Button className="flex-1" onClick={meet}>Open {name}</Button>
          </CardFooter>
        </Card>
      </Shell>
    )
  }

  return (
    <Shell>
      <Card className="w-full max-w-2xl shadow-lg">
        <CardHeader className="grid-cols-[auto_1fr] items-center gap-x-4">
          <Lace state="alert" size={56} decorative className="row-span-2" />
          <CardTitle className="text-xl">Here's what {name} learned about {startup}</CardTitle>
          <CardDescription>Confirm what's right and fix what's off: {name} works from these.</CardDescription>
        </CardHeader>
        <CardContent>
          <LaceFactReview facts={setup.facts} onReview={(id, verdict) => void setup.review(id, verdict)}
                          onCorrect={(id, claim) => void setup.correct(id, claim)} />
          {setup.error && <p className="mt-3 text-sm text-destructive" role="alert">{setup.error}</p>}
        </CardContent>
        <CardFooter>
          <Button className="w-full" onClick={meet}>Looks right, meet {name}</Button>
        </CardFooter>
      </Card>
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-1 items-center justify-center px-4 py-10">{children}</div>
}
