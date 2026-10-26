import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Check, Loader2, X } from "lucide-react"
import { toast } from "sonner"

import { Lace } from "@/components/lace-mascot"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import type { LaceInviteDto } from "@/lib/api"
import { answerInvite } from "@/lib/laces-store"

const MASCOT_PX = 72
const ROLE_SAID = { owner: "its owner", admin: "an admin", member: "a member" } as const

/** A Lace this person was invited to: who asked, as what, and Accept or
 * Decline. None of the Lace shows until they accept. */
export function LaceInviteGate({ invite }: { invite: LaceInviteDto }) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState<"accept" | "decline" | null>(null)
  const answer = async (choice: "accept" | "decline") => {
    setBusy(choice)
    try {
      await answerInvite(invite.lace_id, choice)
      if (choice === "decline") navigate("/", { replace: true })
    } catch (err) {
      toast.error("Couldn't answer the invite", { description: err instanceof Error ? err.message : String(err) })
      setBusy(null)
    }
  }
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md text-center shadow-lg">
        <CardHeader className="justify-items-center">
          <Lace state="alert" size={MASCOT_PX} title={invite.lace_name} />
          <CardTitle className="mt-2 text-xl">Join {invite.lace_name}?</CardTitle>
          <CardDescription className="text-balance">
            {invite.invited_by ?? "Someone"} invited you to {invite.startup_name ?? invite.website}'s Lace as{" "}
            {ROLE_SAID[invite.role]}. You'll work with the same Lace as the rest of the team.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">{invite.website}</CardContent>
        <CardFooter className="justify-center gap-2">
          <Button variant="outline" disabled={busy !== null} onClick={() => void answer("decline")}>
            {busy === "decline" ? <Loader2 className="animate-spin" /> : <X />} Decline
          </Button>
          <Button disabled={busy !== null} onClick={() => void answer("accept")}>
            {busy === "accept" ? <Loader2 className="animate-spin" /> : <Check />} Accept
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
