import { useMemo } from "react"
import { Check, Fingerprint, Loader2, ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"

import { SIGNATURE_LABEL, useStoreGoLive } from "./use-store-go-live"
import type { LaceStore } from "./use-lace-store"

/** The last setup step: a check of what's ready, what signing means, and the
 * owner's passkey prompts that open the Store's wallet and let the Lace act. */
export function StoreGoLive({ laceId, name, store, isOwner }: {
  laceId: string
  name: string
  store: LaceStore
  /** Only the Lace's owner signs for its Store. */
  isOwner: boolean
}) {
  const { user } = useAuth()
  const who = useMemo(() => ({
    email: user?.email ?? "owner",
    name: (user?.user_metadata?.full_name as string | undefined) ?? user?.email ?? "Owner",
  }), [user])
  const live = useStoreGoLive(laceId, store.store, who, store.replace)
  const row = store.store
  const onSale = store.offers.filter((o) => o.status === "active").length
  const checks = [
    { done: onSale > 0, label: onSale ? `${onSale} ${onSale === 1 ? "offer" : "offers"} on sale` : "Put at least one offer on sale" },
    { done: true, label: store.payees.length ? `${store.payees.length} ${store.payees.length === 1 ? "payee" : "payees"} share in each sale`
                                             : "No payees: every sale stays in the Store's wallet" },
    { done: true, label: `At most $${row?.daily_budget_usd} sent out a day` },
  ]
  const busy = live.phase === "passkey" || live.phase === "signing" || live.phase === "waiting"
  const progress = live.phase === "passkey" ? "Making a passkey for the Store on this device"
    : live.step ? `${SIGNATURE_LABEL[live.step]}${live.phase === "waiting" ? "…" : ": confirm with your passkey"}` : null
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
          Going live opens a wallet for the Store on NEAR Intents. You sign its rules (the payees and the daily cap)
          with a passkey on this device, then let {name} act inside them. Sales land there, and nothing can be sent
          anywhere else or past the cap without your signature. Keep the passkey: the wallet stays tied to it.
        </p>
      </div>
      {busy && progress && (
        <p role="status" className="flex items-center gap-2 self-end text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> {progress}
        </p>
      )}
      {live.error && <p role="alert" className="self-end text-sm text-destructive">{live.error}</p>}
      <Button className="self-end" disabled={!isOwner || onSale === 0 || busy} onClick={() => void live.start()}>
        <Fingerprint /> {row?.has_owner ? "Sign and go live" : "Make a passkey and go live"}
      </Button>
      {!isOwner && <p className="self-end text-xs text-muted-foreground">Only the Lace's owner signs for its Store.</p>}
    </div>
  )
}
