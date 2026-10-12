import { cn } from '@/lib/utils'

import { KIND_LABEL, KINDS, type AccountKind } from './use-account-kinds'

export function AccountKindFilter({
  kind,
  counts,
  onChange,
}: {
  kind: AccountKind
  counts: Record<AccountKind, number>
  onChange: (kind: AccountKind) => void
}) {
  return (
    <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Filter targets by kind">
      {KINDS.map((k) => (
        <button
          key={k}
          type="button"
          aria-pressed={kind === k}
          onClick={() => onChange(k)}
          className={cn(
            'cursor-pointer rounded-full border px-2.5 py-1 text-xs transition-colors',
            kind === k
              ? 'border-amber-500/60 bg-amber-500/10 text-amber-500'
              : 'border-border text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          )}
        >
          {KIND_LABEL[k]} <span className="tabular-nums">({counts[k]})</span>
        </button>
      ))}
    </div>
  )
}
