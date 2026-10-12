import { useEffect, useMemo } from "react"
import { Navigate, useParams, useSearchParams } from "react-router-dom"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
} from "@/components/ui/breadcrumb"
import { WorkspaceManager } from "@/components/workspace-manager"
// import { DotLottieReact } from '@lottiefiles/dotlottie-react'
import { Package, Globe, Swords, UserCheck, Users } from "lucide-react"
import { SpecialistAvatarGroup } from "@/components/specialist-avatargroup"
import { useWorkspaceSpecialists } from "@/lib/specialists"
import {
  Stepper,
  StepperItem,
  StepperTrigger,
  StepperIndicator,
  StepperSeparator,
  StepperNav,
  StepperTitle,
  StepperPanel,
  StepperDescription,
} from '@/components/ui/stepper'

import { ChainOfThoughtStack, RunCompleteBadge } from '@/features/chain-of-thought/thought'
import { ChainOfThoughtResultDispaly } from '@/features/chain-of-thought/display'
import { cn } from '@/lib/utils'
import type { StepProgress } from '@/lib/agent-run-store'
import { useAutoFollowScroll } from '@/features/chain-of-thought/use-auto-follow-scroll'
import { ActualWorkspace } from '@/features/workspace/actual-workspace'
import { BuyerBadge } from '@/features/workspace/buyer-badge'
import { useAgentRun } from '@/lib/agent-run-store'
import { refetchWorkspaces, useWorkspaces } from '@/lib/workspaces-store'
import { useSession } from '@/lib/session-context'
import type { AgentNode } from '@/lib/api'

/**
 * Duration/easing of the header's specialist-team fade, matched to the tab
 * transition in `actual_workspace.tsx` (`opacity .175s ease`). Keeping the two
 * identical is what makes the handoff read as a single cross-fade rather than
 * two unrelated transitions. Opacity only -- no translate -- because the panel
 * slides `translate-y-[-50%]` and replicating that on a 48px header element
 * would be absurd.
 */
const TEAM_FADE = { duration: 0.175, ease: 'easeOut' } as const

const steps = [
  {
    id: 'details1',
    title: 'Specialist',
    description: 'Building your specialist team',
    icon: (
      <Users />
    )
  },
  {
    id: 'product',
    title: 'Product',
    description: 'Understanding your product/service domain and its positioning',
    icon: (
      <Package />
    )
  },
  {
    id: 'market',
    title: 'Market',
    description: 'Defining your product-market fit',
    icon: (
      <Globe />
    )
  },
  {
    id: 'competition',
    title: 'Competition',
    description: 'Maping competitors and positioning',
    icon: (
      <Swords />
    )
  },
  {
    id: 'gtm',
    title: 'Ideal Customers',
    description: 'Building ICP and finding ideal customers accounts and triggers',
    icon: (
      <UserCheck />
    )
  }
]

const STEP_TO_NODE: Record<string, AgentNode> = {
  details1: "create_specialists",
  product: "understand_offer",
  market: "understand_market",
  competition: "understand_competition",
  gtm: "determine_icp",
}

const AgentRunProductUnderstanding = () => {
  const run = useAgentRun()

  const progress = useMemo<StepProgress[]>(
    () =>
      steps.map((step) => {
        const phase = run.phases[STEP_TO_NODE[step.id]]
        const status: StepProgress["status"] =
          phase === "done" ? "done" : phase === "started" ? "running" : "pending"
        return { stepId: step.id, status }
      }),
    [run.phases],
  )

  const currentStepId =
    progress.find((entry) => entry.status === "running")?.stepId ??
    progress.find((entry) => entry.status === "pending")?.stepId ??
    steps[0].id

  const finished = progress.every((entry) => entry.status === "done")
  const reachedSteps = progress.filter((entry) => entry.status !== 'pending')
  const awaiting = run.stage === "awaiting_input"

  const {
    containerRef: cotScrollRef,
    updateScrollButton: updateCotScrollButton,
    followIfNear: followCotIfNear,
  } = useAutoFollowScroll()

  useEffect(() => {
    followCotIfNear()
  }, [progress, finished, followCotIfNear])

  return (
    <div className='flex min-h-[calc(100vh-3rem)] w-full items-center justify-center'>
      {/* When getting info for first time, show prgoress */}
      <Stepper
        steps={steps}
        value={currentStepId}
        className='flex max-h-[60vh] items-center justify-center gap-5 overflow-hidden max-lg:flex-col max-lg:items-start'
        orientation='vertical'
      >
        {/* Progress only: steps follow the run and are not navigable. */}
        <StepperNav className='pointer-events-none w-60 select-none' aria-disabled>
          {steps.map((step, index) => (
            <StepperItem key={step.id} stepId={step.id} className='relative items-start'>
              <StepperTrigger tabIndex={-1} className='cursor-default items-start gap-2.5 pb-15 last:pb-0'>
                <StepperIndicator
                  className={cn(
                    awaiting && step.id === currentStepId && 'animate-pulse bg-[#FEA853] text-black',
                  )}
                >
                  {index + 1}
                </StepperIndicator>
                <div className='text-left'>
                  <StepperTitle>{step.title}</StepperTitle>
                  <StepperDescription>{step.description}</StepperDescription>
                </div>
              </StepperTrigger>
              {index < steps.length - 1 && (
                <StepperSeparator className='absolute inset-y-0 top-[calc(50%-22px)] left-2 group-data-[orientation=vertical]/stepper-nav:h-15 bg-primary/15' />
              )}
            </StepperItem>
          ))}
        </StepperNav>
        <StepperPanel className='flex w-xs self-stretch text-center text-sm sm:w-116'>
          <div className='bg-muted border-primary/15 flex h-full flex-col items-center gap-5 rounded-lg border-2 border-dashed p-4 md:p-6'>
            <div className='relative min-h-0 w-full flex-1'>
              <div
                ref={cotScrollRef}
                onScroll={updateCotScrollButton}
                className='h-full w-full min-h-0 overflow-y-auto'
              >
                <div className='w-full space-y-2'>
                  {awaiting && (
                    <div className='flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-600'>
                      <span className='h-2 w-2 shrink-0 rounded-full bg-amber-500 animate-pulse' />
                      Waiting for your input to continue…
                    </div>
                  )}
                  <ChainOfThoughtStack steps={reachedSteps} results={run.phaseResults} />
                  {finished && <RunCompleteBadge />}
                </div>
              </div>
            </div>

            <div className='flex min-h-0 w-full flex-[2] flex-col justify-center'>
              <ChainOfThoughtResultDispaly progress={progress} results={run.phaseResults} />
            </div>
          </div>
        </StepperPanel>
      </Stepper>
    </div>
  )
}

export default function Workspace() {
  const { workspace_id: workspaceIdParam } = useParams<{ workspace_id: string }>()
  const { workspaces } = useWorkspaces()
  const run = useAgentRun()
  const { setSession } = useSession()

  // Fetch on mount and refetch on route changes; the store also refetches
  // when a discovery run creates a workspace and after optimistic mutations.
  useEffect(() => {
    void refetchWorkspaces()
  }, [workspaceIdParam])

  const workspace = workspaceIdParam
    ? workspaces.find((item) => item.id === workspaceIdParam)
    : undefined

  // Move the confirmed session into context once the run finishes so the
  // actual workspace (product tabs, chat) renders with the real snapshot.
  useEffect(() => {
    if (run.stage === "completed" && run.sessionId && run.snapshot) {
      setSession({
        sessionId: run.sessionId,
        workspaceId: run.workspaceId,
        product: run.snapshot,
      })
    }
  }, [run.stage, run.sessionId, run.workspaceId, run.snapshot, setSession])

  const runBelongsToWorkspace =
    run.workspaceId !== null &&
    workspaceIdParam !== undefined &&
    run.workspaceId === workspaceIdParam
  const runActive =
    run.stage === "running" ||
    run.stage === "awaiting_input" ||
    run.stage === "connecting"
  const showStepper = runActive && runBelongsToWorkspace
  const runFailed = run.stage === "error" && runBelongsToWorkspace

  // Same hook the agent tab uses, so the two can't disagree about who the team
  // is (see `useSpecialistTeam`).
  const headerSpecialists = useWorkspaceSpecialists(workspaceIdParam)

  // The active tab lives in the query string, written by `actual_workspace`.
  // Reading it here avoids lifting that state up or threading a prop through
  // the tab component, and it survives reload/deep-link for free.
  const [searchParams] = useSearchParams()
  const agentTabActive = searchParams.get('tab') === 'agent'
  const reduceMotion = useReducedMotion()

  // Both non-idle states render the team somewhere else, so the header stands
  // down for either one: the agent tab always has its own group mounted
  // (`keepMounted`), and while a run is in flight the stepper renders one too
  // (see `ChainOfThoughtResultDispaly`). `showStepper` is checked first
  // because it unmounts the tab strip entirely, which leaves `?tab=agent` in
  // the URL pointing at a tab that no longer exists -- ordering it this way
  // keeps the header the single owner whenever nothing else is drawing.
  const showHeaderTeam = !showStepper && !agentTabActive

  // Legacy /workspace (no id) has no real data — send it to the feed.
  if (!workspaceIdParam) {
    return <Navigate to="/feed" replace />
  }

  return (
    <div className="bg-muted">
      {/* Fixed header — stays pinned at the top while content scrolls below */}
      <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b backdrop-blur transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
        <div className="flex items-center gap-2 px-4">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                {workspace ? (
                  <div className="flex items-center gap-2">
                    <WorkspaceManager workspace={workspace} />
                    <BuyerBadge workspaceId={workspace.id} />
                  </div>
                ) : (
                  <span className="max-w-72 truncate px-2 text-sm font-medium">
                    Workspace
                  </span>
                )}
              </BreadcrumbItem>
              {/*
                The <li> stays mounted and only its contents swap, because a
                conditional <li> would take the exiting child down with it and
                the fade-out would never play. Safe here: this list renders no
                `BreadcrumbSeparator`s, so an empty item occupies no space.
              */}
              <BreadcrumbItem>
                <AnimatePresence initial={false}>
                  {showHeaderTeam && headerSpecialists.length > 0 && (
                    <motion.div
                      key="header-team"
                      initial={reduceMotion ? false : { opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{
                        opacity: 0,
                        transition: reduceMotion ? { duration: 0 } : TEAM_FADE,
                      }}
                      transition={TEAM_FADE}
                    >
                      <div className="flex items-center justify-center gap-4">
                        <SpecialistAvatarGroup specialists={headerSpecialists} />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
      </header>

      {runFailed && (
        <div
          role="alert"
          className="mx-4 mt-3 flex items-center justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive"
        >
          <span>{run.error ?? "The agent run failed."}</span>
        </div>
      )}

      {/* Product Understanding steps — live progress while the agent runs */}
      {showStepper && <AgentRunProductUnderstanding />}

      {/* The Actual Workspace */}
      {!showStepper && <ActualWorkspace workspaceId={workspaceIdParam} />}

    </div>
  )
}
