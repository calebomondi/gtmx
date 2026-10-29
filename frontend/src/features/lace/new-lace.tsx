import { useEffect, useRef, useState, type FormEvent } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Lace, type LaceState } from "@/components/lace-mascot"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { ApiError, askToJoinLace, checkLaceClaimed, createLace } from "@/lib/api"
import { refetchLaces } from "@/lib/laces-store"
import { isWebsite } from "@/lib/validation"
import { usePageTitle } from "@/lib/use-page-title"

import { useEyeTarget } from "./use-eye-target"

const MASCOT_PX = 96
// How long the mascot perks up after a keystroke in its name.
const NAME_PERK_MS = 900

/** Name a Lace and give it the startup's website; it starts reading at once.
 * The mascot watches: the pointer, or the text as it is typed. */
export default function NewLace() {
  usePageTitle("New Lace")
  const navigate = useNavigate()
  const [name, setName] = useState("")
  // Back from a site that couldn't be read: its address, to check and fix.
  const [params] = useSearchParams()
  const [website, setWebsite] = useState(() => params.get("website") ?? "")
  const [websiteTouched, setWebsiteTouched] = useState(false)
  const websiteOk = isWebsite(website)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // The startup already has a Lace: the domain, to ask to join it instead.
  const [taken, setTaken] = useState<string | null>(null)
  const [asked, setAsked] = useState(false)
  const [mood, setMood] = useState<LaceState>("idle")
  const mascot = useRef<HTMLDivElement>(null)
  const form = useRef<HTMLFormElement>(null)
  const perk = useRef<number | undefined>(undefined)
  const look = useEyeTarget(mascot, form)

  useEffect(() => () => window.clearTimeout(perk.current), [])

  const onName = (value: string) => {
    setName(value)
    // Hearing its name: a short alert, settling back to idle.
    setMood("alert")
    window.clearTimeout(perk.current)
    perk.current = window.setTimeout(() => setMood("idle"), NAME_PERK_MS)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const { lace, run_id } = await createLace(name.trim(), website.trim())
      void refetchLaces()
      navigate(`/lace/${lace.id}/setup?run=${run_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setSubmitting(false)
      if (err instanceof ApiError && err.status === 409) {
        const claim = await checkLaceClaimed(website.trim()).catch(() => null)
        setTaken(claim?.taken ? claim.domain : null)
      }
    }
  }

  const askToJoin = async () => {
    setSubmitting(true)
    try {
      await askToJoinLace(website.trim())
      setAsked(true)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md shadow-lg">
        {/* The form is the card's only child, so it carries the card's spacing. */}
        <form ref={form} onSubmit={submit} className="flex flex-col gap-(--card-spacing)">
          <CardHeader className="justify-items-center text-center">
            <div ref={mascot} className="mb-2">
              <Lace state={submitting ? "thinking" : mood} size={MASCOT_PX} look={submitting ? null : look}
                    title="Your new Lace" />
            </div>
            <CardTitle className="text-xl">Create your Lace</CardTitle>
            <CardDescription className="text-balance">
              Your Lace reads your website to learn what you sell, then spots opportunities, finds leads and partners,
              watches competitors, and drafts your outreach and replies.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="lace-name">Name your Lace</FieldLabel>
                <Input id="lace-name" value={name} onChange={(e) => onName(e.target.value)} placeholder="Ada"
                       maxLength={60} autoComplete="off" required />
              </Field>
              <Field>
                <FieldLabel htmlFor="lace-website">Your startup's website</FieldLabel>
                <Input id="lace-website" value={website} onBlur={() => setWebsiteTouched(true)}
                       aria-invalid={websiteTouched && !!website.trim() && !websiteOk}
                       onChange={(e) => { setWebsite(e.target.value); setTaken(null); setAsked(false) }}
                       placeholder="acme.com" inputMode="url" autoComplete="url" required />
                {websiteTouched && website.trim() && !websiteOk && (
                  <FieldError>Enter your startup's website, e.g. acme.com</FieldError>
                )}
              </Field>
              {error && <FieldError>{error}</FieldError>}
              {asked && (
                <p className="text-sm text-muted-foreground" role="status">
                  Asked. The people on {taken}'s Lace will see it and can let you in; it then appears in your sidebar.
                </p>
              )}
            </FieldGroup>
          </CardContent>
          <CardFooter>
            {taken ? (
              <Button type="button" className="w-full" disabled={submitting || asked} onClick={() => void askToJoin()}>
                {submitting && <Loader2 className="animate-spin" />} {asked ? "Asked to join" : `Ask to join ${taken}'s Lace`}
              </Button>
            ) : (
              <Button type="submit" className="w-full" disabled={submitting || !name.trim() || !websiteOk}>
                {submitting && <Loader2 className="animate-spin" />} {submitting ? "Opening your site…" : "Create My Lace"}
              </Button>
            )}
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
