import { Sparkles } from "lucide-react"

import { PlatformIcon } from "@/components/platform-icon"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { PLATFORM_LABEL, type Platform } from "@/lib/platforms"

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

/** "Ask an app": the quick asks by app, from the dock above the input. */
export function AskAnApp({ asks, onAsk, busy }: { asks: QuickAsk[]; onAsk: (text: string) => void; busy: boolean }) {
  if (asks.length === 0) return null
  const byApp = new Map<Platform, QuickAsk[]>()
  for (const ask of asks) byApp.set(ask.platform, [...(byApp.get(ask.platform) ?? []), ask])
  return (
    <Popover>
      <PopoverTrigger render={
        <button type="button" disabled={busy}
                className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-xs transition-all hover:border-theme/60 disabled:cursor-not-allowed disabled:opacity-50" />
      }>
        <Sparkles className="size-3.5 text-muted-foreground" /> Ask an app
      </PopoverTrigger>
      <PopoverContent side="top" sideOffset={10} className="flex w-80 flex-col gap-3">
        {[...byApp.entries()].map(([platform, items]) => (
          <div key={platform} className="flex flex-col gap-1">
            <p className="flex items-center gap-1.5 text-xs font-medium">
              <PlatformIcon platform={platform} className="size-4" /> {PLATFORM_LABEL[platform]}
            </p>
            {items.map((ask) => (
              <button key={ask.label} type="button" disabled={busy} onClick={() => onAsk(ask.text)}
                      className="cursor-pointer rounded-md px-2 py-1 text-left text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50">
                {ask.label}
              </button>
            ))}
          </div>
        ))}
      </PopoverContent>
    </Popover>
  )
}
