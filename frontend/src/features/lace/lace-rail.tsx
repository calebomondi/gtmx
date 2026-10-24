import type { ReactNode } from "react"
import { Blocks, MessagesSquare, Newspaper } from "lucide-react"

import { Lace, type LaceState } from "@/components/lace-mascot"
import { cn } from "@/lib/utils"

import type { LaceTab } from "./lace-tabs"

interface RailProps {
  tab: LaceTab
  onSelect: (tab: LaceTab) => void
  name: string
  mascot: LaceState
  /** Messages waiting on the founder: drafts to send, replies to read. */
  waiting: number
  /** Feed activity the founder has not seen. */
  unread: number
  /** The Lace is searching (Feed) or drafting (Messaging) in the background. */
  feedBusy: boolean
  messagingBusy: boolean
  /** Actions in the founder's apps waiting for their approval. */
  appsWaiting: number
  className?: string
}

function RoundButton({ active, label, onClick, children, count = 0, busy = false, className }: {
  active: boolean
  label: string
  onClick: () => void
  children: ReactNode
  count?: number
  busy?: boolean
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={count ? `${label}, ${count} waiting` : label}
      aria-current={active ? "page" : undefined}
      title={label}
      className={cn(
        "relative grid size-10 shrink-0 cursor-pointer place-items-center rounded-full border transition-colors",
        active
          ? "border-theme bg-theme/15 text-theme shadow-sm"
          : "border-border bg-background text-muted-foreground hover:border-theme/50 hover:text-foreground",
        className,
      )}
    >
      {children}
      {count > 0 && (
        <span className="absolute -top-1 -right-1 grid h-4 min-w-4 place-items-center rounded-full bg-theme px-1 text-[10px] font-medium text-neutral-900 tabular-nums">
          {count > 99 ? "99+" : count}
        </span>
      )}
      {busy && count === 0 && (
        <span aria-hidden className="absolute top-0 right-0 size-2 animate-pulse rounded-full bg-theme" />
      )}
    </button>
  )
}

function Buttons({ tab, onSelect, name, mascot, waiting, unread, feedBusy, messagingBusy, appsWaiting }: RailProps) {
  return (
    <>
      <RoundButton active={tab === "chat"} label={`Chat with ${name}`} onClick={() => onSelect("chat")}
                   className="overflow-hidden p-0">
        {/* The mascot fills the button: it is the Lace you talk to. */}
        <Lace state={mascot} size={38} decorative className="rounded-full" />
      </RoundButton>
      <RoundButton active={tab === "feed"} label="Feed" count={unread} busy={feedBusy} onClick={() => onSelect("feed")}>
        <Newspaper className="size-4" />
      </RoundButton>
      <RoundButton active={tab === "messaging"} label="Messaging" count={waiting} busy={messagingBusy}
                   onClick={() => onSelect("messaging")}>
        <MessagesSquare className="size-4" />
      </RoundButton>
      <RoundButton active={tab === "apps"} label="Apps" count={appsWaiting} onClick={() => onSelect("apps")}>
        <Blocks className="size-4" />
      </RoundButton>
    </>
  )
}

/** Tablet and up: a slim pill of the buttons, beside the content. */
export function LaceRail(props: RailProps) {
  return (
    <nav aria-label={`${props.name}'s places`}
         className={cn("flex flex-col items-center gap-2 rounded-full border bg-muted/60 p-1.5 shadow-sm backdrop-blur", props.className)}>
      <Buttons {...props} />
    </nav>
  )
}

/** Phones: the same buttons in a bar at the bottom, in thumb reach. */
export function LaceTabBar(props: RailProps) {
  return (
    <nav aria-label={`${props.name}'s places`}
         className={cn("flex justify-center gap-6 border-t bg-background/95 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur", props.className)}>
      <Buttons {...props} />
    </nav>
  )
}
