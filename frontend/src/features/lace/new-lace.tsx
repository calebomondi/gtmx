import { useEffect, useRef, useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Lace, type LaceState } from "@/components/lace-mascot"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { createLace } from "@/lib/api"
import { refetchLaces } from "@/lib/laces-store"

import { useEyeTarget } from "./use-eye-target"

const MASCOT_PX = 96
// How long the mascot perks up after a keystroke in its name.
const NAME_PERK_MS = 900

/** Name a Lace and give it the startup's website; it starts reading at once.
 * The mascot watches: the pointer, or the text as it is typed. */
export default function NewLace() {
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [website, setWebsite] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
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
      const { lace } = await createLace(name.trim(), website.trim())
      void refetchLaces()
      navigate(`/lace/${lace.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
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
              Your Lace reads your website, learns what you sell, then finds your customers and helps you reach them.
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
                <Input id="lace-website" value={website} onChange={(e) => setWebsite(e.target.value)}
                       placeholder="acme.com" inputMode="url" autoComplete="url" required />
                <FieldDescription>Your Lace starts here: it reads the site to learn your offer.</FieldDescription>
              </Field>
              {error && <FieldError>{error}</FieldError>}
            </FieldGroup>
          </CardContent>
          <CardFooter>
            <Button type="submit" className="w-full" disabled={submitting || !name.trim() || !website.trim()}>
              {submitting && <Loader2 className="animate-spin" />} Create My Lace
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
