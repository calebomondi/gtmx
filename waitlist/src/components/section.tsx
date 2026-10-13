import type { ReactNode } from 'react'

/** A page section: a small mono label, a headline, then its content. */
export function Section({
  id,
  label,
  title,
  intro,
  children,
}: {
  id?: string
  label: string
  title: string
  intro?: string
  children: ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-line py-16 sm:py-24">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <p className="font-mono text-xs uppercase tracking-wider text-brand-ink">{label}</p>
        <h2 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{title}</h2>
        {intro && <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted">{intro}</p>}
        <div className="mt-10 sm:mt-12">{children}</div>
      </div>
    </section>
  )
}
