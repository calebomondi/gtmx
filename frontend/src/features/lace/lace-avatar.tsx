import { Lace, type LaceState } from "@/components/lace-mascot"

/** A Lace's face beside its words and in its header. */
/** The mascot beside each of the Lace's replies in a chat: a little smaller
 * than elsewhere, so the conversation leads. */
export const REPLY_AVATAR_SIZE = 26

export function LaceAvatar({ state = "idle", animated = true, size = 32, className }: {
  state?: LaceState
  /** Off for the many avatars down a conversation, so only the header moves. */
  animated?: boolean
  size?: number
  className?: string
}) {
  return <Lace state={state} size={size} animated={animated} decorative className={className} />
}
