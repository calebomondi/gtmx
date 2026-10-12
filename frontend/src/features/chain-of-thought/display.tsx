import { useEffect, type ReactNode } from 'react'
import { ArrowDown } from 'lucide-react'
import {
  SpecialistsSkeleton,
  ProductUnderstandSkeleton,
  MarketSkeleton,
  CompetitionSkeleton,
  IcpSkeleton,
} from '@/features/chain-of-thought/skeletons/index'
import { useAutoFollowScroll } from './use-auto-follow-scroll'
import type { PhaseResults, StepProgress } from '@/lib/agent-run-store'
import { CompetitionPanel, IcpPanel, MarketPanel, ProductDomainPanel, SpecialistsPanel } from './phase-panels'

export function ChainOfThoughtResultDispaly({
  progress,
  results,
}: {
  progress: StepProgress[]
  results?: PhaseResults
}) {
  const { containerRef, showScrollButton, updateScrollButton, scrollToBottom, followIfNear } = useAutoFollowScroll()

  useEffect(() => {
    followIfNear()
  }, [progress, followIfNear])

  const stepSections: { stepId: string; done: ReactNode; skeleton: ReactNode }[] = [
    {
      stepId: 'details1',
      done: results?.create_specialists ? (
        <SpecialistsPanel team={results.create_specialists} />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <SpecialistsSkeleton />
        </div>
      ),
      skeleton: <SpecialistsSkeleton />,
    },
    {
      stepId: 'product',
      done: results?.understand_offer ? (
        <ProductDomainPanel text={results.understand_offer} />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <ProductUnderstandSkeleton />
        </div>
      ),
      skeleton: <ProductUnderstandSkeleton />,
    },
    {
      stepId: 'market',
      done: results?.understand_market?.market_data ? (
        <MarketPanel
          fit={results.understand_market.product_market_fit_understanding}
          data={results.understand_market.market_data}
        />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <MarketSkeleton />
        </div>
      ),
      skeleton: <MarketSkeleton />,
    },
    {
      stepId: 'competition',
      done: results?.understand_competition ? (
        <CompetitionPanel swod={results.understand_competition.swod} profile={results.understand_competition.profile} />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <CompetitionSkeleton />
        </div>
      ),
      skeleton: <CompetitionSkeleton />,
    },
    {
      stepId: 'gtm',
      done: results?.determine_icp ? (
        <IcpPanel data={results.determine_icp} />
      ) : (
        <div className="w-full max-w-md rounded-xl p-4">
          <IcpSkeleton />
        </div>
      ),
      skeleton: <IcpSkeleton />,
    },
  ]

  const statusByStep = new Map(progress.map((entry) => [entry.stepId, entry.status]))

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        onScroll={updateScrollButton}
        className="grid h-full w-full min-h-0 place-items-center overflow-y-auto p-2"
      >
        <div className="w-full space-y-1">
          {stepSections.map((section) => {
            const status = statusByStep.get(section.stepId)

            if (status === 'done') {
              return <div key={section.stepId}>{section.done}</div>
            }

            if (status === 'running') {
              return (
                <div key={section.stepId} className="w-full max-w-md rounded-xl p-4">
                  {section.skeleton}
                </div>
              )
            }

            return null
          })}
        </div>
      </div>
      {showScrollButton && (
        <button
          type="button"
          onClick={scrollToBottom}
          aria-label="Scroll to bottom"
          title="Scroll to bottom"
          className="bg-background/95 text-foreground hover:bg-muted absolute right-4 bottom-4 z-10 inline-flex size-9 items-center justify-center rounded-full border shadow-md backdrop-blur-sm transition-colors"
        >
          <ArrowDown className="size-4" />
        </button>
      )}
    </div>
  )
}
