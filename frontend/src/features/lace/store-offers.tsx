import { useState, type FormEvent } from "react"
import { Plus } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { OfferDelivery, OfferDto, OfferInput } from "@/lib/api"

import { Choice } from "./lace-brief"
import { centsFrom, DELIVERY_LABEL, formatPrice, OFFER_STATUS_LABEL } from "./store-model"

const EMPTY = { title: "", price: "", delivery: "link" as OfferDelivery, url: "", note: "", description: "" }

/** A new offer: what it is, its price, and how a paid order is fulfilled. */
function OfferForm({ onAdd, onCancel }: { onAdd: (offer: OfferInput) => Promise<boolean>; onCancel: () => void }) {
  const [draft, setDraft] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const cents = centsFrom(draft.price)
  const ready = draft.title.trim() && cents !== null && cents >= 100 && (draft.delivery === "service" || draft.url.trim())

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!ready || cents === null) return
    setSaving(true)
    const added = await onAdd({
      title: draft.title.trim(), description: draft.description.trim(), price_cents: cents,
      delivery: draft.delivery, delivery_url: draft.delivery === "link" ? draft.url.trim() : null,
      delivery_note: draft.note.trim(),
    })
    setSaving(false)
    if (added) setDraft(EMPTY)
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="rounded-lg border p-4">
      <FieldGroup>
        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <Field>
            <FieldLabel htmlFor="offer-title">What it is</FieldLabel>
            <Input id="offer-title" value={draft.title} placeholder="Pitch deck template"
                   onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          </Field>
          <Field>
            <FieldLabel htmlFor="offer-price">Price (USD)</FieldLabel>
            <Input id="offer-price" inputMode="decimal" value={draft.price} placeholder="29"
                   aria-invalid={draft.price !== "" && (cents === null || cents < 100)}
                   onChange={(e) => setDraft({ ...draft, price: e.target.value })} />
          </Field>
        </div>
        <Field>
          <FieldLabel htmlFor="offer-description">Description</FieldLabel>
          <Textarea id="offer-description" rows={2} value={draft.description}
                    placeholder="What the buyer gets, in a sentence or two."
                    onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
        </Field>
        <Field>
          <FieldLabel>How it's delivered</FieldLabel>
          <div className="flex flex-wrap gap-2">
            {(["link", "service"] as const).map((delivery) => (
              <Choice key={delivery} active={draft.delivery === delivery} onClick={() => setDraft({ ...draft, delivery })}>
                {delivery === "link" ? "A private link" : "A service we deliver"}
              </Choice>
            ))}
          </div>
        </Field>
        {draft.delivery === "link" && (
          <Field>
            <FieldLabel htmlFor="offer-url">The link the buyer receives</FieldLabel>
            <Input id="offer-url" type="url" value={draft.url} placeholder="https://..."
                   onChange={(e) => setDraft({ ...draft, url: e.target.value })} />
            <FieldDescription>Emailed once the payment arrives. It never shows on the storefront.</FieldDescription>
          </Field>
        )}
        <Field>
          <FieldLabel htmlFor="offer-note">
            {draft.delivery === "link" ? "A note with the link (optional)" : "What happens after they pay"}
          </FieldLabel>
          <Textarea id="offer-note" rows={2} value={draft.note}
                    placeholder={draft.delivery === "link" ? "Duplicate it to your drive to edit."
                                                           : "We'll email you within a day to book the session."}
                    onChange={(e) => setDraft({ ...draft, note: e.target.value })} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button type="submit" disabled={!ready || saving}>Add offer</Button>
        </div>
      </FieldGroup>
    </form>
  )
}

function OfferRow({ offer, onStatus }: { offer: OfferDto; onStatus: (status: OfferDto["status"]) => void }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
          {offer.title}
          <Badge variant={offer.status === "active" ? "default" : "outline"}>{OFFER_STATUS_LABEL[offer.status]}</Badge>
          {offer.drafted_by_lace && <Badge variant="outline">Drafted by your Lace</Badge>}
        </p>
        <p className="text-xs text-muted-foreground">{formatPrice(offer.price_cents)} · {DELIVERY_LABEL[offer.delivery]}</p>
      </div>
      <div className="flex gap-1">
        {offer.status !== "active" && <Button size="sm" variant="outline" onClick={() => onStatus("active")}>Put on sale</Button>}
        {offer.status === "active" && <Button size="sm" variant="ghost" onClick={() => onStatus("draft")}>Take off sale</Button>}
        {offer.status !== "archived" && <Button size="sm" variant="ghost" onClick={() => onStatus("archived")}>Archive</Button>}
      </div>
    </li>
  )
}

/** What the Store sells. Offers start as drafts; a person puts each on sale. */
export function StoreOffers({ offers, onAdd, onUpdate }: {
  offers: OfferDto[]
  onAdd: (offer: OfferInput) => Promise<boolean>
  onUpdate: (offerId: string, update: Partial<OfferInput>) => Promise<boolean>
}) {
  const [adding, setAdding] = useState(offers.length === 0)
  const shown = offers.filter((o) => o.status !== "archived")
  const add = async (offer: OfferInput) => {
    const added = await onAdd(offer)
    if (added) setAdding(false)
    return added
  }
  return (
    <div className="flex flex-col gap-3">
      {shown.length > 0 && (
        <ul className="divide-y">
          {shown.map((offer) => (
            <OfferRow key={offer.id} offer={offer} onStatus={(status) => void onUpdate(offer.id, { status })} />
          ))}
        </ul>
      )}
      {adding
        ? <OfferForm onAdd={add} onCancel={() => setAdding(false)} />
        : <Button variant="outline" className="self-start" onClick={() => setAdding(true)}><Plus /> Add an offer</Button>}
    </div>
  )
}
