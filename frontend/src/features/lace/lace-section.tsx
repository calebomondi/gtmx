import type { ReactNode } from "react"
import { Loader2 } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

/** One titled block of a Lace's Feed or Messaging tab. `busy` shows the Lace
 * is working on it in the background. */
export function LaceSection({ title, description, busy = false, children }: {
  title: string
  description: string
  busy?: boolean
  children: ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {title}
          {busy && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Working on it" />}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
