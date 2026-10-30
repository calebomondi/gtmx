import type { ReactNode } from 'react'

/** The hero's showcase frame: an orange sheet offset behind a card with a
 * black status bar. Holds the app's screenshot or the product recording. */
export function DemoFrame({
  status,
  live,
  detail,
  children,
}: {
  status: string
  /** Blink the status dot, as while something is working. */
  live: boolean
  detail: string
  children: ReactNode
}) {
  return (
    <div className="relative">
      {/* An orange sheet behind the card, like a brief laid on a folder. */}
      <div aria-hidden className="absolute inset-0 translate-x-3 translate-y-3 rounded-2xl bg-brand sm:translate-x-4 sm:translate-y-4" />
      <figure className="relative overflow-hidden rounded-2xl border border-ink/10 bg-panel shadow-card">
        <figcaption className="flex items-center justify-between gap-3 bg-ink px-4 py-3">
          <span className="flex shrink-0 items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-brand">
            <span aria-hidden className={`size-1.5 rounded-full bg-brand ${live ? 'caret' : ''}`} />
            {status}
          </span>
          <span className="truncate font-mono text-[11px] text-night-muted">{detail}</span>
        </figcaption>
        {children}
      </figure>
    </div>
  )
}
