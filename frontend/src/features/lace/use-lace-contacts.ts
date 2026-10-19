import { useEffect, useState } from "react"

import { listLaceContacts, type ContactDto } from "@/lib/api"

/** The people at a Lace's target accounts, refetched when `refreshKey`
 * changes (accounts or contacts were found). */
export function useLaceContacts(laceId: string, refreshKey: string) {
  const [contacts, setContacts] = useState<ContactDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listLaceContacts(laceId)
      .then((rows) => {
        if (cancelled) return
        setContacts(rows)
        setError(null)
      })
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [laceId, refreshKey])

  return { contacts, loading, error }
}

/** Contacts whose name, title, account or email holds `query`. */
export function filterContacts(contacts: ContactDto[], query: string): ContactDto[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return contacts
  return contacts.filter((c) => [c.name, c.title, c.account_name, c.email]
    .some((field) => field?.toLowerCase().includes(needle)))
}
