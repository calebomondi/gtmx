import { useState, type ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Stepper, StepperIndicator, StepperItem, StepperNav, StepperSeparator, StepperTitle, StepperTrigger,
} from "@/components/ui/stepper"
import type { LaceRole } from "@/lib/api"

import { formatShare, STORE_STATUS_BADGE } from "./store-model"
import { StoreGoLive } from "./store-go-live"
import { StoreOffers } from "./store-offers"
import { StoreRules } from "./store-rules"
import { StoreSplit } from "./store-split"
import type { LaceStore } from "./use-lace-store"

type SetupStep = "sell" | "split" | "rules" | "live"

const STEPS: { id: SetupStep; title: string }[] = [
  { id: "sell", title: "What you sell" },
  { id: "split", title: "Where money goes" },
  { id: "rules", title: "Rules" },
  { id: "live", title: "Go live" },
]

function StepCard({ title, about, children }: { title: string; about: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{about}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

/** A Store not yet selling: what it sells, who shares in each sale, its
 * rules, then going live. */
function StoreSetup({ laceId, name, store, role }: { laceId: string; name: string; store: LaceStore; role: LaceRole }) {
  const [step, setStep] = useState<SetupStep>(store.offers.length ? "split" : "sell")
  const row = store.store
  if (!row) return null
  const body: Record<SetupStep, ReactNode> = {
    sell: (
      <StepCard title="What you sell" about={`Digital products and services ${name} sells for you, at a fixed price.`}>
        <StoreOffers offers={store.offers} onAdd={store.addOffer} onUpdate={store.updateOffer} />
      </StepCard>
    ),
    split: (
      <StepCard title="Where money goes" about="Who shares in each sale, and how much. Every sale is credited in USDC.">
        <StoreSplit payees={store.payees} onSave={store.savePayees} />
      </StepCard>
    ),
    rules: (
      <StepCard title="Rules" about={`What the storefront says, and the limit only people can change. ${name} never can.`}>
        <StoreRules store={row} onSave={store.update} />
      </StepCard>
    ),
    live: (
      <StepCard title="Go live" about="One last check before the Store opens.">
        <StoreGoLive laceId={laceId} name={name} store={store} isOwner={role === "owner"} />
      </StepCard>
    ),
  }
  return (
    <div className="flex flex-col gap-6">
      <Stepper steps={STEPS} value={step} onValueChange={(next) => setStep(next as SetupStep)}>
        <StepperNav>
          {STEPS.map(({ id, title }, index) => (
            <StepperItem key={id} stepId={id}>
              <StepperTrigger className="flex flex-col items-center gap-1.5 sm:flex-row">
                <StepperIndicator>{index + 1}</StepperIndicator>
                <StepperTitle className="text-xs sm:text-sm">{title}</StepperTitle>
              </StepperTrigger>
              {index < STEPS.length - 1 && <StepperSeparator className="mx-2" />}
            </StepperItem>
          ))}
        </StepperNav>
      </Stepper>
      {/* Members see the setup; admins and the owner change it. */}
      <fieldset disabled={role === "member"} className="min-w-0">{body[step]}</fieldset>
    </div>
  )
}

/** A live Store, until its own tabs (orders, ledger) arrive: where its money
 * sits and the rules it keeps to. */
function StoreLive({ store }: { store: LaceStore }) {
  const row = store.store
  if (!row) return null
  const facts = [
    { label: "Sales land in", value: row.wallet_account_id ?? "Its NEAR Intents wallet" },
    { label: "Signed by", value: row.owner_account_id ?? "The owner's passkey" },
    { label: "Payees", value: store.payees.map((p) => `${p.label} ${formatShare(p.share_bps)}`).join(", ") || "None" },
    { label: "Daily cap", value: `$${row.daily_budget_usd}` },
  ]
  return (
    <Card>
      <CardHeader>
        <CardTitle>Open for sales</CardTitle>
        <CardDescription>Its rules are in the wallet's signed policy: only a new signature from the owner changes them.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3 text-sm sm:grid-cols-[10rem_1fr]">
          {facts.map((fact) => (
            <div key={fact.label} className="contents">
              <dt className="text-muted-foreground">{fact.label}</dt>
              <dd className="min-w-0 truncate font-mono text-xs leading-5 sm:text-sm">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

/** A Lace's Store tab. Until it goes live, the setup; after, what it sold. */
export function LaceStoreTab({ laceId, name, role, store }: { laceId: string; name: string; role: LaceRole; store: LaceStore }) {
  if (store.loading) return <div className="mx-auto w-full max-w-4xl p-4"><Skeleton className="h-64 w-full" /></div>
  const row = store.store
  if (!row) return null
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="flex items-center gap-2 text-lg font-medium">
            {row.name} <Badge variant="outline">{STORE_STATUS_BADGE[row.status]}</Badge>
          </h2>
          <p className="text-sm text-muted-foreground">{row.tagline || `What ${name} sells, and the rules it keeps to.`}</p>
        </div>
      </header>
      {store.error && <p role="alert" className="text-sm text-destructive">{store.error}</p>}
      {row.status === "setup" && <StoreSetup laceId={laceId} name={name} store={store} role={role} />}
      {row.status !== "setup" && <StoreLive store={store} />}
    </div>
  )
}
