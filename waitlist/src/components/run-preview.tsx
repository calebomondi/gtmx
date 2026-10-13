import { useEffect, useState } from 'react'

import { EXAMPLE_COMPANY, EXAMPLE_DRAFT, EXAMPLE_STEPS, type StepKind } from './example-run'

const STEP_MS = 1100
const HOLD_MS = 6500

const MARK: Record<StepKind, { glyph: string; tone: string }> = {
  read: { glyph: '◦', tone: 'text-muted' },
  market: { glyph: '◦', tone: 'text-muted' },
  kept: { glyph: '+', tone: 'text-kept' },
  dropped: { glyph: '−', tone: 'text-dropped' },
  account: { glyph: '→', tone: 'text-brand-ink' },
  draft: { glyph: '✓', tone: 'text-kept' },
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** The hero's proof: a GTMX run playing out step by step, ending on a drafted
 * first message. Loops; shows the finished run at once for reduced motion. */
export function RunPreview() {
  const total = EXAMPLE_STEPS.length
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? total : 1))

  useEffect(() => {
    if (prefersReducedMotion()) return
    const timer = window.setTimeout(
      () => setShown((n) => (n >= total ? 1 : n + 1)),
      shown >= total ? HOLD_MS : STEP_MS,
    )
    return () => window.clearTimeout(timer)
  }, [shown, total])

  const finished = shown >= total

  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-panel shadow-[0_1px_0_rgba(20,22,26,0.04),0_12px_32px_-16px_rgba(20,22,26,0.18)]">
      <figcaption className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <span className="shrink-0 font-mono text-[11px] whitespace-nowrap uppercase tracking-wider text-muted">Example run</span>
        <span className="truncate font-mono text-[11px] text-muted">{EXAMPLE_COMPANY}</span>
      </figcaption>
      <ol className="flex min-h-[248px] flex-col gap-2.5 px-4 py-4" aria-live="off">
        {EXAMPLE_STEPS.slice(0, shown).map((step, i) => (
          <li key={i} className="animate-step-in grid grid-cols-[1rem_1fr] gap-x-2 text-sm">
            <span aria-hidden className={`font-mono ${MARK[step.kind].tone}`}>
              {MARK[step.kind].glyph}
            </span>
            <span className="min-w-0">
              <span className="block text-[13px] text-muted">{step.label}</span>
              <span className="block font-medium">{step.finding}</span>
            </span>
          </li>
        ))}
      </ol>
      <div
        className={`border-t border-line bg-paper px-4 py-4 transition-opacity duration-500 ${finished ? 'opacity-100' : 'opacity-0'}`}
        aria-hidden={!finished}
      >
        <p className="font-mono text-[11px] uppercase tracking-wider text-muted">Draft · email</p>
        <p className="mt-1.5 text-sm font-semibold">{EXAMPLE_DRAFT.subject}</p>
        <p className="mt-1 text-[13px] leading-relaxed text-ink/80">{EXAMPLE_DRAFT.body}</p>
        <div className="mt-3 flex items-center gap-2">
          <span className="rounded-md bg-ink px-3 py-1.5 text-xs font-semibold text-paper">Send</span>
          <span className="text-xs text-muted">Only when you say so.</span>
        </div>
      </div>
    </figure>
  )
}
