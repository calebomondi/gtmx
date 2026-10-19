import { useState } from "react"
import { Mail, Search } from "lucide-react"

import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

import { filterContacts, useLaceContacts } from "./use-lace-contacts"

/** The people the Lace found at its target accounts, with how to reach each. */
export function LaceContacts({ laceId, refreshKey }: { laceId: string; refreshKey: string }) {
  const { contacts, loading, error } = useLaceContacts(laceId, refreshKey)
  const [query, setQuery] = useState("")
  const shown = filterContacts(contacts, query)

  if (loading) return <Skeleton className="h-24 w-full" />
  if (error) return <p className="text-sm text-destructive" role="alert">{error}</p>
  if (contacts.length === 0) {
    return <p className="text-sm text-muted-foreground">None yet. Ask your Lace to find who to contact at your target accounts.</p>
  }
  return (
    <div className="flex flex-col gap-3">
      <InputGroup>
        <InputGroupAddon><Search /></InputGroupAddon>
        <InputGroupInput value={query} onChange={(e) => setQuery(e.target.value)}
                         placeholder="Search by name, title, company or email" aria-label="Search contacts" />
      </InputGroup>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Person</TableHead>
            <TableHead>Account</TableHead>
            <TableHead className="text-right">Reach</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {shown.map((c) => (
            <TableRow key={c.id}>
              <TableCell className="max-w-56 whitespace-normal">
                <p className="font-medium">{c.name ?? c.email ?? "Unnamed"}</p>
                {c.title && <p className="text-xs text-muted-foreground">{c.title}</p>}
              </TableCell>
              <TableCell className="max-w-40 truncate">{c.account_name}</TableCell>
              <TableCell>
                <div className="flex justify-end gap-1">
                  {c.email && (
                    <a href={`mailto:${c.email}`} title={c.email} aria-label={`Email ${c.name ?? c.email}`}
                       className="grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">
                      <Mail className="size-4" />
                    </a>
                  )}
                  {c.linkedin && (
                    <a href={c.linkedin} target="_blank" rel="noreferrer" aria-label={`${c.name ?? "Contact"} on LinkedIn`}
                       className="grid size-8 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">
                      {/* lucide ships no brand marks: LinkedIn's "in", set in type. */}
                      <span aria-hidden className="text-xs font-bold">in</span>
                    </a>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {shown.length === 0 && <p className="text-sm text-muted-foreground">No contact matches “{query}”.</p>}
    </div>
  )
}
