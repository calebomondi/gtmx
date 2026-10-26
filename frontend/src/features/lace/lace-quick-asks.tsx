import { PlatformIcon } from "@/components/platform-icon"

import type { QuickAsk } from "./quick-asks"

function AskButton({ ask, onAsk, disabled }: { ask: QuickAsk; onAsk: (text: string) => void; disabled: boolean }) {
  return (
    <button type="button" disabled={disabled} onClick={() => onAsk(ask.text)} title={ask.text}
            className="flex cursor-pointer items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-left text-xs transition-colors hover:border-theme/60 disabled:cursor-not-allowed disabled:opacity-50">
      <PlatformIcon platform={ask.platform} className="size-4" />
      {ask.label}
    </button>
  )
}

/** The quick asks as chips, for a conversation that hasn't started. */
export function QuickAskChips({ asks, onAsk, disabled }: { asks: QuickAsk[]; onAsk: (text: string) => void; disabled: boolean }) {
  if (asks.length === 0) return null
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">Or ask about your apps:</p>
      <div className="flex flex-wrap gap-2">
        {asks.map((ask) => <AskButton key={`${ask.platform}:${ask.label}`} ask={ask} onAsk={onAsk} disabled={disabled} />)}
      </div>
    </div>
  )
}
