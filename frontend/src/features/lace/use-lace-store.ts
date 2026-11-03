import { useCallback, useEffect, useState } from "react"

import {
  addOffer, getStore, listOffers, listPayees, setPayees, setStoreShown, updateOffer, updateStore,
  type OfferDto, type OfferInput, type PayeeDto, type PayeeInput, type StoreDto, type StoreUpdate,
} from "@/lib/api"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export interface LaceStore {
  /** Null before anyone turned the Store on. */
  store: StoreDto | null
  offers: OfferDto[]
  payees: PayeeDto[]
  loading: boolean
  error: string | null
  /** Each returns false when it didn't save; `error` then says why. */
  setShown: (shown: boolean) => Promise<boolean>
  update: (update: StoreUpdate) => Promise<boolean>
  addOffer: (offer: OfferInput) => Promise<boolean>
  updateOffer: (offerId: string, update: Partial<OfferInput>) => Promise<boolean>
  savePayees: (payees: PayeeInput[]) => Promise<boolean>
  /** Show the Store as the server last returned it (after a signature). */
  replace: (store: StoreDto) => void
}

/** A Lace's Store, its offers and its revenue split. */
export function useLaceStore(laceId: string): LaceStore {
  const [store, setStore] = useState<StoreDto | null>(null)
  const [offers, setOffers] = useState<OfferDto[]>([])
  const [payees, setPayeeRows] = useState<PayeeDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getStore(laceId)
      .then(async (found) => {
        const [items, split] = found ? await Promise.all([listOffers(laceId), listPayees(laceId)]) : [[], []]
        if (cancelled) return
        setStore(found)
        setOffers(items)
        setPayeeRows(split)
      })
      .catch((err) => !cancelled && setError(message(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [laceId])

  /** Run one change; on failure keep what's shown and say why. */
  const attempt = useCallback(async (change: () => Promise<void>) => {
    try {
      await change()
      setError(null)
      return true
    } catch (err) {
      setError(message(err))
      return false
    }
  }, [])

  const setShown = useCallback((shown: boolean) => attempt(async () => {
    setStore(await setStoreShown(laceId, shown))
  }), [attempt, laceId])

  const update = useCallback((change: StoreUpdate) => attempt(async () => {
    setStore(await updateStore(laceId, change))
  }), [attempt, laceId])

  const add = useCallback((offer: OfferInput) => attempt(async () => {
    const saved = await addOffer(laceId, offer)
    setOffers((prev) => [...prev, saved])
  }), [attempt, laceId])

  const change = useCallback((offerId: string, fields: Partial<OfferInput>) => attempt(async () => {
    const saved = await updateOffer(laceId, offerId, fields)
    setOffers((prev) => prev.map((o) => (o.id === offerId ? saved : o)))
  }), [attempt, laceId])

  const savePayees = useCallback((split: PayeeInput[]) => attempt(async () => {
    setPayeeRows(await setPayees(laceId, split))
  }), [attempt, laceId])

  return { store, offers, payees, loading, error, setShown, update, addOffer: add, updateOffer: change, savePayees,
           replace: setStore }
}
