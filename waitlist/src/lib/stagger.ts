import type { CSSProperties } from 'react'

/** Inline style that delays a revealed element by its position in a group. */
export const stagger = (i: number): CSSProperties => ({ '--i': i }) as CSSProperties
