import { Lace, type LaceState } from "@/components/lace-mascot"

/** A Lace's face beside its words and in its header. */
export function LaceAvatar({ state = "idle", animated = true, className }: {
  state?: LaceState
  /** Off for the many avatars down a conversation, so only the header moves. */
  animated?: boolean
  className?: string
}) {
  return <Lace state={state} size={32} animated={animated} decorative className={className} />
}
