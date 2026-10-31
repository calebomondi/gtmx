import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import MultipleSelector, { type Option } from "@/components/ui/multi-select"
import { Skeleton } from "@/components/ui/skeleton"
import { COUNTRY_CODES, countryName } from "@/lib/countries"

import type { LaceRegulations } from "./use-lace-regulations"

// Every place a startup operates in that its searches cover (the server's limit).
const MAX_PLACES = 10

function option(code: string): Option {
  return { value: code, label: countryName(code) }
}

const OPTIONS = COUNTRY_CODES.map(option).sort((a, b) => a.label.localeCompare(b.label))

function day(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
}

/** Where the startup is registered and operates. The Lace searches for the
 * laws that apply only once a founder confirms it here (or in the chat). */
export function LaceJurisdiction({ name, regulations }: { name: string; regulations: LaceRegulations }) {
  const { jurisdiction, loading, error, confirm } = regulations
  // Edits start from what is saved; null until the founder changes something.
  const [draft, setDraft] = useState<{ registered: Option[]; operates: Option[] } | null>(null)
  const [saving, setSaving] = useState(false)
  if (loading) return <Skeleton className="h-24 w-full" />
  const registered = draft?.registered
    ?? (jurisdiction?.registered_in ? [option(jurisdiction.registered_in)] : [])
  const operates = draft?.operates ?? (jurisdiction?.operates_in ?? []).map(option)
  const confirmedAt = jurisdiction?.jurisdiction_confirmed_at
  const save = async () => {
    setSaving(true)
    const ok = await confirm(registered[0]?.value ?? null, operates.map((o) => o.value))
    setSaving(false)
    if (ok) setDraft(null)
  }
  return (
    <FieldGroup className="gap-4">
      <Field>
        <FieldLabel>Registered in</FieldLabel>
        <MultipleSelector value={registered} options={OPTIONS} maxSelected={1} placeholder="Pick a country"
                          hidePlaceholderWhenSelected emptyIndicator={<p className="p-2 text-sm">No such country</p>}
                          onChange={(picked) => setDraft({ registered: picked, operates })} />
        <FieldDescription>Company law and corporate tax apply here.</FieldDescription>
      </Field>
      <Field>
        <FieldLabel>Operates in</FieldLabel>
        <MultipleSelector value={operates} options={OPTIONS} maxSelected={MAX_PLACES} placeholder="Add countries"
                          hidePlaceholderWhenSelected emptyIndicator={<p className="p-2 text-sm">No such country</p>}
                          onChange={(picked) => setDraft({ registered, operates: picked })} />
        <FieldDescription>
          Wherever you have staff, an office or customers: employment, tax, licences and data protection apply there.
        </FieldDescription>
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <Button size="sm" disabled={saving || (registered.length === 0 && operates.length === 0) || (!draft && !!confirmedAt)}
                onClick={() => void save()}>
          {confirmedAt && !draft ? "Confirmed" : "Confirm"}
        </Button>
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {confirmedAt
            ? `Confirmed ${day(confirmedAt)}. ${name} watches the laws that apply in these places.`
            : `Not confirmed yet: ${name} looks for the laws that apply only after you confirm.`}
        </p>
      </div>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </FieldGroup>
  )
}
