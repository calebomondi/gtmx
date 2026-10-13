import type { StepProgress } from '@/lib/agent-run-store'
import { cn } from '@/lib/utils'

/** The run's progress in one compact block, for screens too narrow for the
 * full step list: where it is, what that step does, and a segmented bar. */
export function StepStrip({
  steps,
  progress,
  currentStepId,
  awaiting,
  className,
}: {
  steps: { id: string; title: string; description: string }[]
  progress: StepProgress[]
  currentStepId: string
  awaiting: boolean
  className?: string
}) {
  const index = Math.max(0, steps.findIndex((s) => s.id === currentStepId))
  const step = steps[index]
  return (
    <div className={cn('flex flex-col gap-2 text-left', className)}>
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Step {index + 1} of {steps.length}
      </p>
      <p className="text-base font-semibold">{step.title}</p>
      <p className="text-sm text-muted-foreground">{step.description}</p>
      <ol className="mt-1 flex gap-1.5" aria-label="Progress">
        {progress.map((p, i) => (
          <li
            key={p.stepId}
            aria-label={`${steps[i]?.title}: ${p.status}`}
            className={cn(
              'h-1.5 flex-1 rounded-full',
              p.status === 'done' && 'bg-[#FEA853]',
              p.status === 'running' && cn('bg-[#FEA853]/50', awaiting ? 'animate-pulse' : ''),
              p.status === 'pending' && 'bg-primary/15',
            )}
          />
        ))}
      </ol>
    </div>
  )
}
