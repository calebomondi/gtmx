import { Sparkles } from 'lucide-react'

/** Questions the user can send with one click: follow-ups to the last answer,
 * or starters for an empty conversation. */
export function SuggestionChips({
  suggestions,
  disabled,
  onPick,
}: {
  suggestions: string[]
  disabled: boolean
  onPick: (question: string) => void
}) {
  if (suggestions.length === 0) return null
  return (
    <div className='flex flex-wrap gap-2' role='group' aria-label='Suggested questions'>
      {suggestions.map((question) => (
        <button
          key={question}
          type='button'
          disabled={disabled}
          onClick={() => onPick(question)}
          className='inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/5 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:border-amber-500/60 hover:bg-amber-500/10 disabled:cursor-not-allowed disabled:opacity-50'
        >
          <Sparkles className='size-3 shrink-0 text-amber-500' />
          {question}
        </button>
      ))}
    </div>
  )
}
