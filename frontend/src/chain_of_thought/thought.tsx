import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtItem,
  ChainOfThoughtStep,
  ChainOfThoughtTrigger,
} from "@/components/ui/chain-of-thought"
import { Check, LoaderCircle } from "lucide-react"
import { type ReactNode } from "react"
import type { PhaseResults, StepStatus } from "@/lib/agent-run-store"

interface Thought {
  title: string
  items: ReactNode[]
}

const STEP_TITLES: Record<string, string> = {
  details1: "Assembling your specialist team",
  product: "Understanding your product domain",
  market: "Evaluating product-market fit",
  competition: "Scanning the competitive landscape",
  gtm: "Building your ideal customer profile",
}

function statusIcon(status: StepStatus) {
  if (status === "running") {
    return <LoaderCircle className="size-3 animate-spin" />
  }
  if (status === "done") {
    return <Check className="size-3 text-primary" />
  }
  return undefined
}

/** Real per-step thoughts derived from streamed agent phase results. */
function buildRealThought(
  stepId: string,
  results: PhaseResults,
): Thought | null {
  if (stepId === "details1") {
    const team = results.create_specialists
    if (!team) return null
    const members = [
      team.product_or_service_specialist,
      team.market_specialist,
      team.competition_specialist,
      team.gtm_specialist,
    ]
    return {
      title: "Assembling your specialist team",
      items: members.map(
        (member) => `${member.name} — ${member.role_title}: ${member.focus}`,
      ),
    }
  }

  if (stepId === "product") {
    if (!results.understand_product) return null
    return {
      title: "Understanding your product domain",
      items: [results.understand_product],
    }
  }

  if (stepId === "market") {
    const market = results.understand_market
    if (!market) return null
    const data = market.market_data
    const items: ReactNode[] = []
    if (market.product_market_fit_understanding) {
      items.push(market.product_market_fit_understanding)
    }
    if (data.buyer_type) items.push(`Buyer type: ${data.buyer_type}`)
    if (data.category) items.push(`Category: ${data.category}`)
    if (data.market_fit) items.push(`Market fit: ${data.market_fit}`)
    if (data.target_audience) items.push(`Audience: ${data.target_audience}`)
    return { title: "Evaluating product-market fit", items }
  }

  if (stepId === "competition") {
    const competition = results.understand_competition
    if (!competition) return null
    const items: ReactNode[] = competition.competitors.map(
      (competitor) =>
        `Tracking ${competitor.name}${competitor.website ? ` (${competitor.website})` : ""}`,
    )
    if (competition.differentiators.length > 0) {
      items.push(`Differentiators: ${competition.differentiators.join(", ")}`)
    }
    return { title: "Scanning the competitive landscape", items }
  }

  if (stepId === "gtm") {
    const icp = results.determine_icp
    if (!icp) return null
    const items: ReactNode[] = []
    if (icp.buyer_type) items.push(`Buyer type: ${icp.buyer_type}`)
    if (icp.industries.length > 0) {
      items.push(`Targeting industries: ${icp.industries.join(", ")}`)
    }
    if (icp.buyer_titles.length > 0) {
      items.push(`Priority titles: ${icp.buyer_titles.join(", ")}`)
    }
    if (icp.pain_signals.length > 0) {
      items.push(`Pain signals: ${icp.pain_signals.join(", ")}`)
    }
    return { title: "Building your ideal customer profile", items }
  }

  return null
}

export function ChainOfThoughtStack({
  steps,
  results,
}: {
  steps: { stepId: string; status: StepStatus }[]
  results?: PhaseResults
}) {
  return (
    <div className="w-full p-3 grid place-items-center">
      <ChainOfThought>
        {steps.map(({ stepId, status }) => {
          const thought: Thought =
            (results ? buildRealThought(stepId, results) : null) ?? {
              title: STEP_TITLES[stepId] ?? stepId,
              items: [
                status === "running"
                  ? "Working on this step…"
                  : "No details for this step yet.",
              ],
            }

          return (
            <ChainOfThoughtStep key={stepId}>
              <ChainOfThoughtTrigger
                leftIcon={statusIcon(status)}
                swapIconOnHover={status !== "running"}
              >
                {thought.title}
              </ChainOfThoughtTrigger>
              <ChainOfThoughtContent>
                {thought.items.map((item, index) => (
                  <ChainOfThoughtItem key={index}>{item}</ChainOfThoughtItem>
                ))}
              </ChainOfThoughtContent>
            </ChainOfThoughtStep>
          )
        })}
      </ChainOfThought>
    </div>
  )
}

export function RunCompleteBadge() {
  return (
    <div className="flex items-center justify-center gap-2 py-3 text-center text-xs text-muted-foreground">
      <span className="bg-primary/10 text-primary flex size-5 items-center justify-center rounded-full">
        <Check className="size-3" />
      </span>
      <span>Agent run complete</span>
    </div>
  )
}