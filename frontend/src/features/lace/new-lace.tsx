import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createLace } from "@/lib/api"

/** Name a Lace and give it the startup's website; it starts reading at once. */
export default function NewLace() {
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [website, setWebsite] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const { lace } = await createLace(name.trim(), website.trim())
      navigate(`/lace/${lace.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-10">
      <form onSubmit={submit} className="flex w-full max-w-sm flex-col gap-5">
        <div className="flex flex-col gap-1 text-center">
          <h1 className="text-xl font-medium">Create a Lace</h1>
          <p className="text-sm text-muted-foreground">
            Your Lace reads your website, learns what you sell, then helps you find customers and reach them.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="lace-name">Name your Lace</Label>
          <Input id="lace-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ada" maxLength={60} required />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="lace-website">Your startup's website</Label>
          <Input id="lace-website" value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="acme.com" inputMode="url" required />
        </div>
        {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        <Button type="submit" disabled={submitting || !name.trim() || !website.trim()}>
          {submitting && <Loader2 className="animate-spin" />} Create
        </Button>
      </form>
    </div>
  )
}
