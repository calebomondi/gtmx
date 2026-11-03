import { ArrowRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Field, FieldContent, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"

import { STORE_STATUS_LABEL } from "./store-model"
import type { LaceStore } from "./use-lace-store"

/** The Store in a Lace's settings: whether its tab shows on the rail, and
 * where it stands. Turning it on the first time makes the Store. */
export function LaceStoreSettings({ name, store, onOpen }: {
  name: string
  store: LaceStore
  /** Go to the Store's tab. */
  onOpen: () => void
}) {
  if (store.loading) return <Skeleton className="h-16 w-full" />
  const row = store.store
  return (
    <div className="flex flex-col gap-5">
      <Field orientation="horizontal">
        <FieldContent>
          <FieldLabel htmlFor="store-shown">Show the Store</FieldLabel>
          <FieldDescription>
            Adds a Store tab next to the chat, where you set up what {name} sells, who shares in each sale and
            the rules it keeps to. Hiding it again keeps everything as it is.
          </FieldDescription>
        </FieldContent>
        <Switch id="store-shown" checked={row?.shown ?? false} onCheckedChange={(on) => void store.setShown(on)} />
      </Field>
      {row && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/30 px-4 py-3">
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium">{row.name}</p>
            <p className="text-xs text-muted-foreground">
              {row.frozen_at ? "Wallet frozen: nothing can move money" : STORE_STATUS_LABEL[row.status]}
            </p>
          </div>
          {row.shown && <Button size="sm" variant="outline" onClick={onOpen}>Open the Store <ArrowRight /></Button>}
        </div>
      )}
      {store.error && <p role="alert" className="text-sm text-destructive">{store.error}</p>}
    </div>
  )
}
