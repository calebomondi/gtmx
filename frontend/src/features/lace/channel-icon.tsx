import { Mail } from "lucide-react"

import { PlatformIcon } from "@/components/platform-icon"
import type { OutreachChannel } from "@/lib/api"
import { cn } from "@/lib/utils"

/** A way to reach someone, as its mark: a mail glyph, else the platform's. */
export function ChannelIcon({ channel, className }: { channel: OutreachChannel; className?: string }) {
  if (channel === "email") return <Mail className={cn("size-4", className)} />
  return <PlatformIcon platform={channel} className={cn("size-4 rounded-sm text-[10px]", className)} />
}
