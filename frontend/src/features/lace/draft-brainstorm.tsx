import { useState } from "react"
import { ArrowUp, Loader2 } from "lucide-react"

import { Lace } from "@/components/lace-mascot"
import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/ui/markdown"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Textarea } from "@/components/ui/textarea"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { LaceOutreachDto } from "@/lib/api"
import { cn } from "@/lib/utils"

import { aboutDraft, workingOnDraft } from "./draft-exchanges"
import type { LaceChat } from "./use-lace-chat"
import { useScrollToEnd } from "./use-scroll-to-end"

const IDEAS = ["Make it shorter", "Warmer, less salesy", "Lead with their news"]

/** The Lace beside a draft's Send: a small chat about this one draft, in
 * which the Lace answers and rewrites the draft in place. It is the Lace's
 * one conversation, so it remembers; the main chat folds these exchanges. */
export function DraftBrainstorm({ draft, chat, name }: { draft: LaceOutreachDto; chat: LaceChat; name: string }) {
  const [text, setText] = useState("")
  const exchange = aboutDraft(chat.messages, draft.id)
  const busy = workingOnDraft(chat, draft.id)
  const scroller = useScrollToEnd<HTMLDivElement>(draft.id, exchange.length + (busy ? 1 : 0))

  const submit = (value: string) => {
    const said = value.trim()
    if (!said || chat.working) return
    setText("")
    void chat.send(said, [], draft.id)
  }

  return (
    <Popover>
      <Tooltip>
        <TooltipTrigger render={
          <PopoverTrigger render={
            <button type="button" aria-label={`Brainstorm with ${name}`}
                    className="grid size-8 cursor-pointer place-items-center rounded-full transition-colors hover:bg-theme/15" />
          } />
        }>
          <Lace state={busy ? "thinking" : "idle"} size={26} decorative />
        </TooltipTrigger>
        <TooltipContent>Brainstorm with {name}</TooltipContent>
      </Tooltip>
      <PopoverContent side="top" align="start" className="w-80 gap-2 p-3">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Lace state={busy ? "thinking" : "alert"} size={20} decorative /> Brainstorm with {name}
        </p>
        <div ref={scroller} className="flex max-h-64 flex-col gap-2 overflow-y-auto text-sm">
          {exchange.length === 0 && !busy && (
            <p className="text-xs text-muted-foreground">
              Say what should change, or ask what would make it land. {name} rewrites the draft in place.
            </p>
          )}
          {exchange.map((m, i) => (
            <div key={i} className={cn("max-w-[90%] rounded-lg px-2.5 py-1.5",
                                       m.role === "founder" ? "self-end bg-theme/15" : "self-start bg-muted")}>
              {m.role === "founder" ? m.content : <Markdown>{m.content}</Markdown>}
            </div>
          ))}
          {busy && (
            <p className="flex items-center gap-1.5 self-start text-xs text-muted-foreground" aria-live="polite">
              <Loader2 className="size-3 animate-spin" /> {chat.step ?? "Thinking"}
            </p>
          )}
        </div>
        {exchange.length === 0 && (
          <div className="flex flex-wrap gap-1.5">
            {IDEAS.map((idea) => (
              <button key={idea} type="button" onClick={() => submit(idea)} disabled={chat.working}
                      className="cursor-pointer rounded-full border border-dashed px-2 py-0.5 text-[11px] text-muted-foreground hover:border-theme/50 hover:text-foreground disabled:cursor-default disabled:opacity-50">
                {idea}
              </button>
            ))}
          </div>
        )}
        <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); submit(text) }}>
          <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={2000}
                    aria-label={`Message to ${name} about this draft`} placeholder="What should change?"
                    className="min-h-0 resize-none text-sm"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault()
                        submit(text)
                      }
                    }} />
          <Button type="submit" size="icon-sm" disabled={!text.trim() || chat.working} aria-label="Send">
            <ArrowUp />
          </Button>
        </form>
        {chat.working && !busy && <p className="text-xs text-muted-foreground">{name} is busy with something else; try in a moment.</p>}
      </PopoverContent>
    </Popover>
  )
}
