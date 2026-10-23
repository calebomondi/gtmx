import type { ReactNode } from 'react'

/** A toggle pill: pressed is filled with ink. */
function Pill({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`cursor-pointer rounded-full border px-3.5 py-1.5 text-sm transition ${
        pressed ? 'border-ink bg-ink text-paper' : 'border-line bg-panel text-ink hover:border-ink/40'
      }`}
    >
      {children}
    </button>
  )
}

/** A row of single-choice pills; choosing the selected one again clears it. */
export function Choice<T extends string>({
  legend,
  options,
  value,
  onChange,
}: {
  legend: string
  options: { value: T; label: string }[]
  value: T | undefined
  onChange: (value: T | undefined) => void
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-sm font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <Pill
            key={option.value}
            pressed={option.value === value}
            onClick={() => onChange(option.value === value ? undefined : option.value)}
          >
            {option.label}
          </Pill>
        ))}
      </div>
    </fieldset>
  )
}
