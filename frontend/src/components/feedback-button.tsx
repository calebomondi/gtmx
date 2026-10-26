import { useState } from "react"
import { matchPath, useLocation } from "react-router-dom"
import { MessageSquare } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { FEEDBACK_MAX_CHARS, sendFeedback } from "@/lib/api"

const LABEL = "Suggestions & feedback"

/** The sidebar's way to tell the team what works, what doesn't and what to
 * add: a square icon button like the theme toggle, named on hover. It goes
 * with the page you were on, so it can be read in context. */
export function FeedbackButton() {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState("")
  const [sending, setSending] = useState(false)
  const laceId = matchPath("/lace/:lace_id/*", pathname)?.params.lace_id ?? null

  const send = async () => {
    setSending(true)
    try {
      await sendFeedback(text.trim(), pathname, laceId)
      toast.success("Thanks! The team will read it.")
      setText("")
      setOpen(false)
    } catch (err) {
      toast.error("Couldn't send it", { description: err instanceof Error ? err.message : String(err) })
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <Tooltip>
        <TooltipTrigger render={<Button variant="outline" size="icon" type="button" aria-label={LABEL} onClick={() => setOpen(true)} />}>
          <MessageSquare className="h-[1.2rem] w-[1.2rem]" />
        </TooltipTrigger>
        <TooltipContent side="right">{LABEL}</TooltipContent>
      </Tooltip>
      <Dialog open={open} onOpenChange={(next) => !sending && setOpen(next)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{LABEL}</DialogTitle>
            <DialogDescription>
              Something you'd like, something that got in your way, or something that worked. It goes straight to the
              Thalace team.
            </DialogDescription>
          </DialogHeader>
          <Field className="px-4">
            <FieldLabel htmlFor="feedback-text" className="sr-only">Your feedback</FieldLabel>
            <Textarea id="feedback-text" value={text} onChange={(e) => setText(e.target.value)} rows={6}
                      maxLength={FEEDBACK_MAX_CHARS} placeholder="What should we know?" autoFocus />
          </Field>
          <DialogFooter className="sm:flex-row sm:justify-end">
            <DialogClose render={<Button variant="outline" disabled={sending} />}>Cancel</DialogClose>
            <Button onClick={() => void send()} disabled={sending || !text.trim()}>
              {sending ? "Sending…" : "Send"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
