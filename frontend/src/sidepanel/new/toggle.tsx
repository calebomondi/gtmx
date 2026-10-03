import * as React from 'react'

import { ToggleGroup, ToggleGroupItem } from '@/components/ui/motion-toggle-group'
import { cn } from '@/lib/utils'

/**
 * Where the discovery agent sources its evidence from. Deliberately not
 * "do you have a website" — plenty of teams have both, and the second branch
 * is a perfectly good starting point for them.
 */
export type SourceMode = 'website' | 'social'

type SourceOption = {
  value: SourceMode
  label: string
  hint: string
}

const SOURCE_OPTIONS: SourceOption[] = [
  {
    value: 'website',
    label: 'Website',
    hint: 'Point me at your product page',
  },
  {
    value: 'social',
    label: 'Social accounts',
    hint: 'Link the accounts you post from',
  },
]

type SourceToggleProps = {
  value: SourceMode
  onValueChange: (value: SourceMode) => void
  className?: string
}

export function SourceToggle({
  value,
  onValueChange,
  className,
}: SourceToggleProps) {
  // The group mirrors `value` into internal state from an effect keyed on the
  // array identity, so this has to stay referentially stable — an inline
  // `[value]` would change identity every render and loop.
  const selected = React.useMemo(() => [value], [value])

  const active =
    SOURCE_OPTIONS.find((option) => option.value === value) ?? SOURCE_OPTIONS[0]

  return (
    <div className={cn('my-5', className)}>
      <ToggleGroup
        type="single"
        value={selected}
        onValueChange={(next) => {
          const picked = next[0]
          if (picked) onValueChange(picked as SourceMode)
        }}
        activeClassName="bg-background rounded-lg"
        spacing={0}
        className="bg-primary/10 w-full justify-between rounded-lg p-0.5"
      >
        {SOURCE_OPTIONS.map((option) => (
          <ToggleGroupItem
            key={option.value}
            value={option.value}
            aria-label={option.label}
            className="group-data-[spacing=0]/toggle-group:px-0.5 h-8 min-w-7 flex-1 cursor-pointer text-sm font-medium"
          >
            {option.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      {/* Reserve the line so the card doesn't jump when the hint swaps. */}
      <p className="mt-2.5 min-h-4 text-center text-xs text-muted-foreground">
        {active.hint}
      </p>
    </div>
  )
}

export default SourceToggle
