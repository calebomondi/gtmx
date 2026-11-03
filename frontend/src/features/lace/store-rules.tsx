import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group"
import { Textarea } from "@/components/ui/textarea"
import type { StoreDto, StoreUpdate } from "@/lib/api"

import { STOREFRONT_PREFIX } from "./store-model"

const SLUG = /^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$/

/** The storefront's name and address, and the one rule a person sets for
 * money going out: how much the Store may send in a day. Once live, the
 * address and the cap are fixed until the owner signs new rules. */
export function StoreRules({ store, onSave }: { store: StoreDto; onSave: (update: StoreUpdate) => Promise<boolean> }) {
  const [draft, setDraft] = useState({ name: store.name, tagline: store.tagline, slug: store.slug,
                                       budget: store.daily_budget_usd })
  const [saved, setSaved] = useState(false)
  const settingUp = store.status === "setup"
  const budget = Number(draft.budget)
  const valid = draft.name.trim() && SLUG.test(draft.slug) && Number.isFinite(budget) && budget >= 1 && budget <= 100_000
  const set = (field: keyof typeof draft) => (value: string) => {
    setSaved(false)
    setDraft({ ...draft, [field]: value })
  }

  const save = async () => {
    const update: StoreUpdate = { name: draft.name.trim(), tagline: draft.tagline.trim() }
    if (settingUp) Object.assign(update, { slug: draft.slug, daily_budget_usd: budget.toFixed(2) })
    setSaved(await onSave(update))
  }

  return (
    <FieldGroup>
      <Field>
        <FieldLabel htmlFor="store-name">Store name</FieldLabel>
        <Input id="store-name" value={draft.name} onChange={(e) => set("name")(e.target.value)} />
      </Field>
      <Field>
        <FieldLabel htmlFor="store-tagline">One line about it</FieldLabel>
        <Textarea id="store-tagline" rows={2} value={draft.tagline} placeholder="Templates and playbooks for early-stage founders."
                  onChange={(e) => set("tagline")(e.target.value)} />
      </Field>
      <Field>
        <FieldLabel htmlFor="store-slug">Address</FieldLabel>
        <InputGroup>
          <InputGroupAddon><InputGroupText>{STOREFRONT_PREFIX}</InputGroupText></InputGroupAddon>
          <InputGroupInput id="store-slug" value={draft.slug} disabled={!settingUp} aria-invalid={!SLUG.test(draft.slug)}
                           onChange={(e) => set("slug")(e.target.value.toLowerCase())} />
        </InputGroup>
        <FieldDescription>Lowercase letters, numbers and dashes. Fixed once the Store is live, so links keep working.</FieldDescription>
      </Field>
      <Field>
        <FieldLabel htmlFor="store-budget">Most it may send out in a day (USD)</FieldLabel>
        <Input id="store-budget" inputMode="decimal" className="max-w-40" value={draft.budget} disabled={!settingUp}
               aria-invalid={!Number.isFinite(budget) || budget < 1} onChange={(e) => set("budget")(e.target.value)} />
        <FieldDescription>
          Payouts to your team and the Store's own running costs count against it. Your wallet enforces it, so not
          even your Lace can go past it. {!settingUp && "Changing it needs a new signature from the owner."}
        </FieldDescription>
      </Field>
      <Button className="self-end" disabled={!valid} onClick={() => void save()}>{saved ? "Saved" : "Save"}</Button>
    </FieldGroup>
  )
}
