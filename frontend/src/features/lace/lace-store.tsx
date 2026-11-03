import { useState, type ReactNode } from "react"
import { Check, ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Stepper, StepperIndicator, StepperItem, StepperNav, StepperSeparator, StepperTitle, StepperTrigger,
} from "@/components/ui/stepper"
import type { LaceRole } from "@/lib/api"

import { STORE_STATUS_BADGE } from "./store-model"
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

/** The last step: what going live asks of the owner, once the rest is ready. */
function GoLive({ name, store }: { name: string; store: LaceStore }) {
  const onSale = store.offers.filter((o) => o.status === "active").length
  const checks = [
    { done: onSale > 0, label: onSale ? `${onSale} ${onSale === 1 ? "offer" : "offers"} on sale` : "Put at least one offer on sale" },
    { done: true, label: store.payees.length ? `${store.payees.length} ${store.payees.length === 1 ? "payee" : "payees"} share in each sale`
                                             : "No payees: every sale stays in the Store's wallet" },
    { done: true, label: `At most $${store.store?.daily_budget_usd} sent out a day` },
  ]
  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-2">
        {checks.map((check) => (
          <li key={check.label} className="flex items-center gap-2 text-sm">
            <Check className={check.done ? "size-4 text-theme" : "size-4 text-muted-foreground/40"} />
            <span className={check.done ? "" : "text-muted-foreground"}>{check.label}</span>
          </li>
        ))}
      </ul>
      <div className="flex gap-3 rounded-lg border bg-muted/30 p-4 text-sm">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-theme" />
        <p className="text-muted-foreground">
          Going live opens a wallet for the Store on NEAR Intents. The owner signs its rules (the payees and the
          daily cap) once, and then lets {name} act inside them. Sales land there; nothing can be sent anywhere
          else, or past the cap, without a new signature.
        </p>
      </div>
      <Button className="self-end" disabled>Sign and go live</Button>
      <p className="self-end text-xs text-muted-foreground">Wallet signing is being connected next.</p>
    </div>
  )
}

/** A Store not yet selling: what it sells, who shares in each sale, its
 * rules, then going live. */
function StoreSetup({ name, store, manages }: { name: string; store: LaceStore; manages: boolean }) {
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
        <GoLive name={name} store={store} />
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
      <fieldset disabled={!manages} className="min-w-0">{body[step]}</fieldset>
    </div>
  )
}

/** A Lace's Store tab. Until it goes live, the setup; after, what it sold. */
export function LaceStoreTab({ name, role, store }: { name: string; role: LaceRole; store: LaceStore }) {
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
      {row.status === "setup" && <StoreSetup name={name} store={store} manages={role !== "member"} />}
    </div>
  )
}
