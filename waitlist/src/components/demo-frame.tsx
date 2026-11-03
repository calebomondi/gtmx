import type { ReactNode } from 'react'

/** The hero's showcase frame: the recording on a card. */
export function DemoFrame({ children }: { children: ReactNode }) {
  return (
    <div className="relative">
      <figure className="relative overflow-hidden rounded-2xl border border-ink/10 bg-panel shadow-lift">
        {children}
      </figure>
    </div>
  )
}
