import { useState } from "react"
import { Plus, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import type { PayeeDto, PayeeInput, PayeeRoute } from "@/lib/api"

import { Choice } from "./lace-brief"
import { formatShare, keptShare } from "./store-model"

interface Row {
  label: string
  route: PayeeRoute
  chain: string
  address: string
  /** As typed, in percent. */
  percent: string
}

const BLANK: Row = { label: "", route: "transfer", chain: "", address: "", percent: "" }

function rowOf(payee: PayeeDto): Row {
  return { label: payee.label, route: payee.route, chain: payee.chain ?? "", address: payee.address,
           percent: String(payee.share_bps / 100) }
}

/** Basis points from "12.5"; null when it isn't a share. */
function bpsFrom(percent: string): number | null {
  const value = Number(percent)
  if (!percent.trim() || !Number.isFinite(value) || value <= 0 || value > 100) return null
  return Math.round(value * 100)
}

function payeeOf(row: Row): PayeeInput | null {
  const share = bpsFrom(row.percent)
  if (share === null || !row.label.trim() || !row.address.trim()) return null
  if (row.route === "withdraw" && !row.chain.trim()) return null
  return { label: row.label.trim(), route: row.route, chain: row.route === "withdraw" ? row.chain.trim().toLowerCase() : null,
           address: row.address.trim(), share_bps: share }
}

function PayeeRow({ row, index, onChange, onRemove }: {
  row: Row
  index: number
  onChange: (row: Row) => void
  onRemove: () => void
}) {
  const id = (field: string) => `payee-${index}-${field}`
  return (
    <li className="flex flex-col gap-3 rounded-lg border p-3">
      <div className="grid grid-cols-[1fr_5rem_auto] gap-3">
        <Field>
          <FieldLabel htmlFor={id("label")}>Who</FieldLabel>
          <Input id={id("label")} value={row.label} placeholder="Treasury, or a cofounder's name"
                 onChange={(e) => onChange({ ...row, label: e.target.value })} />
        </Field>
        <Field>
          <FieldLabel htmlFor={id("share")}>Share (%)</FieldLabel>
          <Input id={id("share")} inputMode="decimal" value={row.percent} placeholder="50"
                 aria-invalid={row.percent !== "" && bpsFrom(row.percent) === null}
                 onChange={(e) => onChange({ ...row, percent: e.target.value })} />
        </Field>
        <Button variant="ghost" size="icon-sm" className="self-end" aria-label={`Remove ${row.label || "this payee"}`}
                onClick={onRemove}>
          <Trash2 />
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Choice active={row.route === "transfer"} onClick={() => onChange({ ...row, route: "transfer" })}>
          A NEAR account
        </Choice>
        <Choice active={row.route === "withdraw"} onClick={() => onChange({ ...row, route: "withdraw" })}>
          An address on another chain
        </Choice>
      </div>
      <div className={row.route === "withdraw" ? "grid gap-3 sm:grid-cols-[7rem_1fr]" : "grid gap-3"}>
        {row.route === "withdraw" && (
          <Field>
            <FieldLabel htmlFor={id("chain")}>Chain</FieldLabel>
            <Input id={id("chain")} value={row.chain} placeholder="base"
                   onChange={(e) => onChange({ ...row, chain: e.target.value })} />
          </Field>
        )}
        <Field>
          <FieldLabel htmlFor={id("address")}>{row.route === "transfer" ? "NEAR account" : "Address"}</FieldLabel>
          <Input id={id("address")} value={row.address} placeholder={row.route === "transfer" ? "acme.near" : "0x..."}
                 onChange={(e) => onChange({ ...row, address: e.target.value })} />
        </Field>
      </div>
    </li>
  )
}

/** Who shares in each sale. Each destination goes into the policy the
 * founder signs, so the wallet refuses to pay anywhere else. */
export function StoreSplit({ payees, onSave }: { payees: PayeeDto[]; onSave: (payees: PayeeInput[]) => Promise<boolean> }) {
  const [rows, setRows] = useState<Row[]>(() => (payees.length ? payees.map(rowOf) : [BLANK]))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const parsed = rows.map(payeeOf)
  const complete = parsed.every((p) => p !== null)
  const valid = parsed.filter((p): p is PayeeInput => p !== null)
  const kept = keptShare(valid)

  const change = (index: number, row: Row) => {
    setSaved(false)
    setRows((prev) => prev.map((r, i) => (i === index ? row : r)))
  }
  const save = async () => {
    setSaving(true)
    setSaved(await onSave(valid))
    setSaving(false)
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-3">
        {rows.map((row, index) => (
          <PayeeRow key={index} row={row} index={index} onChange={(next) => change(index, next)}
                    onRemove={() => { setSaved(false); setRows((prev) => prev.filter((_, i) => i !== index)) }} />
        ))}
      </ul>
      <Button variant="outline" className="self-start" onClick={() => setRows((prev) => [...prev, BLANK])}>
        <Plus /> Add a payee
      </Button>
      <p className={kept < 0 ? "text-sm text-destructive" : "text-sm text-muted-foreground"}>
        {kept < 0
          ? "The shares add up to more than the whole sale."
          : `${formatShare(kept)} of each sale stays in the Store's wallet, for its running costs and refunds.`}
      </p>
      <Button className="self-end" disabled={!complete || kept < 0 || saving} onClick={() => void save()}>
        {saved ? "Saved" : "Save the split"}
      </Button>
    </div>
  )
}
