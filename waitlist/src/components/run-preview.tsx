import { useEffect, useState } from 'react'

import { EXAMPLE_COMPANY, EXAMPLE_DRAFT, EXAMPLE_STEPS, type StepKind } from './example-run'

// The pace of a working agent: a beat of "thinking", then the finding.
const THINK_MS = 750
const SETTLE_MS = 450
const HOLD_MS = 7000

const MARK: Record<StepKind, { glyph: string; tone: string }> = {
  read: { glyph: '◦', tone: 'text-muted' },
  market: { glyph: '◦', tone: 'text-muted' },
  kept: { glyph: '+', tone: 'text-kept' },
  dropped: { glyph: '×', tone: 'text-dropped' },
  account: { glyph: '→', tone: 'text-brand-ink' },
  draft: { glyph: '✓', tone: 'text-kept' },
}

type Phase = 'thinking' | 'done'

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** The hero's centrepiece: a GTMX run playing out as if the agent is working
 * (each line thinks, then resolves; a false rival is struck out), ending on a
 * drafted first message. Loops. Reduced motion shows the finished run. */
export function RunPreview() {
  const total = EXAMPLE_STEPS.length
  const [state, setState] = useState<{ index: number; phase: Phase }>(() =>
    prefersReducedMotion() ? { index: total - 1, phase: 'done' } : { index: 0, phase: 'thinking' },
  )

  useEffect(() => {
    if (prefersReducedMotion()) return
    const last = state.index >= total - 1 && state.phase === 'done'
    const wait = last ? HOLD_MS : state.phase === 'thinking' ? THINK_MS : SETTLE_MS
    const timer = window.setTimeout(() => {
      setState((s) => {
        if (s.phase === 'thinking') return { ...s, phase: 'done' }
        return s.index >= total - 1 ? { index: 0, phase: 'thinking' } : { index: s.index + 1, phase: 'thinking' }
      })
    }, wait)
    return () => window.clearTimeout(timer)
  }, [state, total])

  const finished = state.index >= total - 1 && state.phase === 'done'

  return (
    <div className="relative">
      {/* An orange sheet behind the card, like a brief laid on a folder. */}
      <div aria-hidden className="absolute inset-0 translate-x-3 translate-y-3 rounded-2xl bg-brand sm:translate-x-4 sm:translate-y-4" />
      <figure className="relative overflow-hidden rounded-2xl border border-ink/10 bg-panel shadow-card">
        <figcaption className="flex items-center justify-between gap-3 bg-ink px-4 py-3">
          <span className="flex shrink-0 items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-brand">
            <span aria-hidden className={`size-1.5 rounded-full bg-brand ${finished ? '' : 'caret'}`} />
            {finished ? 'Run complete' : 'Running'}
          </span>
          <span className="truncate font-mono text-[11px] text-night-muted">Example · {EXAMPLE_COMPANY}</span>
        </figcaption>

        <ol className="flex min-h-[23rem] flex-col gap-3 px-4 py-4 sm:min-h-[21.75rem] sm:px-5" aria-label="Example run">
          {EXAMPLE_STEPS.slice(0, state.index + 1).map((step, i) => {
            const thinking = i === state.index && state.phase === 'thinking'
            return (
              <li key={i} className="animate-step-in grid grid-cols-[1rem_1fr] gap-x-2.5 text-sm">
                <span aria-hidden className={`font-mono ${thinking ? 'text-muted' : MARK[step.kind].tone}`}>
                  {thinking ? '·' : MARK[step.kind].glyph}
                </span>
                <span className="min-w-0">
                  <span className="block text-[13px] text-muted">
                    {step.label}
                    {thinking && <span aria-hidden className="caret ml-0.5 text-brand-ink">▍</span>}
                  </span>
                  {!thinking && (
                    <span className="animate-step-in block font-medium">
                      {/* Its own element: the strike's animation would replace the step-in. */}
                      <span className={step.kind === 'dropped' ? 'strike' : undefined}>{step.finding}</span>
                    </span>
                  )}
                </span>
              </li>
            )
          })}
        </ol>

        <div
          className={`border-t border-line bg-paper px-4 py-4 transition-all duration-500 sm:px-5 ${
            finished ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
          }`}
          aria-hidden={!finished}
        >
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted">Draft · email · for your review</p>
          <p className="mt-1.5 text-sm font-semibold">{EXAMPLE_DRAFT.subject}</p>
          <p className="mt-1 text-[13px] leading-relaxed text-ink/80">{EXAMPLE_DRAFT.body}</p>
          <div className="mt-3 flex items-center gap-2.5">
            <span className={`rounded-md bg-brand px-3.5 py-1.5 text-xs font-semibold text-ink ${finished ? 'send-pulse' : ''}`}>
              Send
            </span>
            <span className="text-xs text-muted">Only when you say so.</span>
          </div>
        </div>
      </figure>
    </div>
  )
}
