import type { ReactNode } from 'react'

import { stagger } from '../lib/stagger'

export type Tone = 'paper' | 'night' | 'brand'

const TONE: Record<Tone, { section: string; label: string; intro: string }> = {
  paper: { section: 'bg-paper text-ink', label: 'text-brand-ink', intro: 'text-muted [&_strong]:text-ink' },
  night: { section: 'on-dark bg-night text-paper', label: 'text-brand', intro: 'text-night-muted [&_strong]:text-paper' },
  brand: { section: 'bg-brand text-ink', label: 'text-ink', intro: 'text-ink/75' },
}

/** A page section: a headline and an intro that rise in as the section
 * scrolls into view, then its content. A mono label above the headline is
 * kept for the few sections it helps find (the pilot, the questions). The tone
 * sets its surface; on paper, `decor` draws the section's own arrangement of
 * Lace squares behind it. */
export function Section({
  id,
  tone = 'paper',
  label,
  title,
  intro,
  decor,
  layout = 'stacked',
  children,
}: {
  id?: string
  tone?: Tone
  label?: string
  title: string
  /** Its key phrase in <strong>, to be caught at a glance. */
  intro?: ReactNode
  /** Background shapes (LaceSquare), clipped to the section. */
  decor?: ReactNode
  /** stacked: the heading above the content. split: on wide screens the
   * heading holds a left column, pinned, beside the content. */
  layout?: 'stacked' | 'split'
  children: ReactNode
}) {
  const t = TONE[tone]
  return (
    // overflow-clip, not hidden: it clips the decor without becoming a scroll
    // container, so How it works' sticky stage still pins.
    <section id={id} className={`relative isolate scroll-mt-14 overflow-clip py-20 sm:py-28 ${t.section}`}>
      {decor && <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">{decor}</div>}
      <div className={`mx-auto max-w-7xl px-5 sm:px-8 ${
        layout === 'split' ? 'lg:grid lg:grid-cols-[0.8fr_1.2fr] lg:gap-16' : ''}`}>
        <div className={layout === 'split' ? 'lg:sticky lg:top-24 lg:self-start' : ''}>
          {label && (
            <p data-reveal className={`mb-4 flex items-center gap-2 font-mono text-xs uppercase tracking-wider ${t.label}`}>
              <span aria-hidden className={`h-px w-6 ${tone === 'brand' ? 'bg-ink' : 'bg-brand'}`} />
              {label}
            </p>
          )}
          <h2
            data-reveal
            style={stagger(1)}
            className="max-w-3xl text-[2rem] leading-[1.08] font-semibold tracking-[-0.03em] text-balance sm:text-5xl"
          >
            {title}
          </h2>
          {intro && (
            <p data-reveal style={stagger(2)} className={`mt-5 max-w-2xl text-lg leading-relaxed [&_strong]:font-semibold ${t.intro}`}>
              {intro}
            </p>
          )}
        </div>
        <div className={layout === 'split' ? 'mt-12 sm:mt-14 lg:mt-0' : 'mt-12 sm:mt-14'}>{children}</div>
      </div>
    </section>
  )
}
