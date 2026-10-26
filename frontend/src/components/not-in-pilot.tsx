import { LogOut, RotateCcw } from "lucide-react"

import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { supabase } from "@/lib/supabase"
import { usePageTitle } from "@/lib/use-page-title"

// The public site, where the waitlist is.
const WAITLIST_URL = "https://thalace.com"

/** For someone signed in who isn't in the closed pilot yet: why they can't
 * go further, and the ways in. */
export function NotInPilot({ email, onRecheck }: { email: string | null; onRecheck: () => void }) {
  usePageTitle("Not in the pilot yet")
  return (
    <div className="grid min-h-dvh place-items-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-xl">You're not in the pilot yet</CardTitle>
          <CardDescription>
            Thalace is in a closed pilot, and we're letting founders in a few at a time. We'll be in touch when it's your
            turn.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm text-muted-foreground">
          <p>
            If a cofounder already uses Thalace, ask them to invite {email ? <strong className="text-foreground">{email}</strong> : "you"} to
            your startup's Lace. You'll be in as soon as you accept.
          </p>
          <p>Not on the waitlist yet? Join it and tell us about your startup.</p>
        </CardContent>
        <CardFooter className="flex flex-wrap gap-2">
          <a href={WAITLIST_URL} className={buttonVariants()}>Join the waitlist</a>
          <Button variant="outline" onClick={onRecheck}><RotateCcw /> Check again</Button>
          <Button variant="ghost" onClick={() => void supabase.auth.signOut()}><LogOut /> Sign out</Button>
        </CardFooter>
      </Card>
    </div>
  )
}
