import type { ReactNode } from 'react'

import { LaceSquare } from './lace-square'

/** The hero's showcase frame: the recording on a card, with two of the page's
 * Lace squares behind it, one at the top-left corner and one at the bottom-right. */
export function DemoFrame({ children }: { children: ReactNode }) {
  return (
    <div className="relative">
      <div aria-hidden>
        <LaceSquare className="top-[-9%] left-[-7%] w-[58%] -rotate-6" />
        <LaceSquare className="right-[-6%] bottom-[-8%] w-[30%] rotate-8" />
      </div>
      <figure className="relative overflow-hidden rounded-2xl border border-ink/10 bg-panel shadow-lift">
        {children}
      </figure>
    </div>
  )
}
