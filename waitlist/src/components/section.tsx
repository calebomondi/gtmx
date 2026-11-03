import type { ReactNode } from 'react'

export type Tone = 'paper' | 'night' | 'brand'

const TONE: Record<Tone, { section: string; intro: string }> = {
  // See-through: the page's backdrop (page-backdrop.tsx) is its paper.
  paper: { section: 'text-ink', intro: 'text-muted' },
  night: { section: 'on-dark bg-night text-paper', intro: 'text-night-muted' },
  brand: { section: 'bg-brand text-ink', intro: 'text-ink/75' },
}

/** A page section: a headline that makes the point, a plain intro, then its
 * content. The tone sets its surface. */
export function Section({
  id,
  tone = 'paper',
  title,
  intro,
  layout = 'stacked',
  children,
}: {
  id?: string
  tone?: Tone
  title: ReactNode
  intro?: ReactNode
  /** stacked: the heading above the content. split: on wide screens the
   * heading holds a left column, pinned, beside the content. */
  layout?: 'stacked' | 'split'
  children: ReactNode
}) {
  const t = TONE[tone]
  return (
    <section id={id} className={`relative isolate scroll-mt-14 py-20 sm:py-28 ${t.section}`}>
      <div className={`mx-auto max-w-7xl px-5 sm:px-8 ${
        layout === 'split' ? 'lg:grid lg:grid-cols-[0.8fr_1.2fr] lg:gap-16' : ''}`}>
        <div data-quiet className={layout === 'split' ? 'lg:sticky lg:top-24 lg:self-start' : ''}>
          <h2
            className="max-w-3xl text-[2rem] leading-[1.08] font-semibold tracking-[-0.03em] text-balance sm:text-5xl"
          >
            {title}
          </h2>
          {intro && (
            <p className={`mt-5 max-w-2xl text-lg leading-relaxed ${t.intro}`}>
              {intro}
            </p>
          )}
        </div>
        <div data-quiet className={layout === 'split' ? 'mt-12 sm:mt-14 lg:mt-0' : 'mt-12 sm:mt-14'}>{children}</div>
      </div>
    </section>
  )
}
