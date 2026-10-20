import { Fragment, useState } from "react"
import { Check, CheckCheck, Mail, Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { ContactDto } from "@/lib/api"

import { byAccount, filterContacts } from "./contacts-model"

const LINK = "grid size-8 cursor-pointer place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"

/** The people the Lace found at saved accounts, by account, with how to reach
 * each. A person (or their email or LinkedIn) opens them: their messages and
 * a way to have the Lace write to them. Nothing is drafted to anyone until
 * the founder approves them: one by one, or everyone at an account at once. */
export function LaceContacts({ contacts, onApprove, onApproveAccount, onOpen }: {
  contacts: ContactDto[]
  onApprove: (contactId: string, approved: boolean) => void
  onApproveAccount: (accountId: string) => void
  onOpen: (contact: ContactDto, channel: "email" | "linkedin" | null) => void
}) {
  const [query, setQuery] = useState("")
  const groups = byAccount(filterContacts(contacts, query))

  if (contacts.length === 0) {
    return <p className="text-sm text-muted-foreground">None yet. Ask your Lace to find who to contact at your saved accounts.</p>
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
            <TableHead className="text-right">Reach</TableHead>
            <TableHead className="w-32 text-right">Outreach</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {groups.map((group) => (
            <Fragment key={group.accountId}>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableCell colSpan={2} className="font-medium">{group.accountName}</TableCell>
                <TableCell className="text-right">
                  {group.waiting > 0 && (
                    <Button size="sm" variant="outline" onClick={() => onApproveAccount(group.accountId)}>
                      <CheckCheck /> Approve all ({group.waiting})
                    </Button>
                  )}
                </TableCell>
              </TableRow>
              {group.people.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="max-w-56 whitespace-normal">
                    <button type="button" onClick={() => onOpen(c, null)}
                            className="cursor-pointer text-left font-medium underline-offset-4 hover:underline">
                      {c.name ?? c.email ?? "Unnamed"}
                    </button>
                    {c.title && <p className="text-xs text-muted-foreground">{c.title}</p>}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      {c.email && (
                        <button type="button" title={`Write to ${c.email}`} aria-label={`Email ${c.name ?? c.email}`}
                                className={LINK} onClick={() => onOpen(c, "email")}>
                          <Mail className="size-4" />
                        </button>
                      )}
                      {c.linkedin && (
                        <button type="button" title="Message on LinkedIn" aria-label={`${c.name ?? "Contact"} on LinkedIn`}
                                className={LINK} onClick={() => onOpen(c, "linkedin")}>
                          {/* lucide ships no brand marks: LinkedIn's "in", set in type. */}
                          <span aria-hidden className="text-xs font-bold">in</span>
                        </button>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {c.approved_at ? (
                      <Button size="sm" variant="ghost" title="Approved for outreach; click to take it back"
                              onClick={() => onApprove(c.id, false)}>
                        <Check /> Approved
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => onApprove(c.id, true)}>Approve</Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </Fragment>
          ))}
        </TableBody>
      </Table>
      {groups.length === 0 && <p className="text-sm text-muted-foreground">No contact matches “{query}”.</p>}
    </div>
  )
}
