import { useState } from "react"
import { Check, Search, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { ContactDto, LaceOutreachDto, OutreachChannel } from "@/lib/api"

import { ChannelIcon } from "./channel-icon"
import { byNewReplies, filterContacts, reachOf, roleAt, unreadByChannel } from "./contacts-model"
import { CHANNEL_LABELS } from "./outreach-threads"
import { UnreadBadge } from "./unread-badge"

const LINK = "grid size-8 cursor-pointer place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"

/** The people the Lace found at saved accounts, one row each with what they
 * do and where, and how to reach them. A person (or one of the ways to reach
 * them) opens them: their messages and a way to have the Lace write to them.
 * Nothing is drafted to anyone until the founder approves them. */
export function LaceContacts({ contacts, outreach, onApprove, onRemove, onOpen }: {
  contacts: ContactDto[]
  /** For the new replies each person has, by channel. */
  outreach: LaceOutreachDto[]
  onApprove: (contactId: string, approved: boolean) => void
  onRemove: (contactId: string) => void
  onOpen: (contact: ContactDto, channel: OutreachChannel | null) => void
}) {
  const [query, setQuery] = useState("")
  const unread = new Map(contacts.map((c) => [c.id, unreadByChannel(outreach, c)]))
  const people = byNewReplies(filterContacts(contacts, query), unread)

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
            <TableHead className="w-10"><span className="sr-only">Remove</span></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {people.map((c) => (
            <TableRow key={c.id}>
              <TableCell className="max-w-56 whitespace-normal">
                <button type="button" onClick={() => onOpen(c, null)}
                        className="cursor-pointer text-left font-medium underline-offset-4 hover:underline">
                  {c.name ?? c.email ?? "Unnamed"}
                </button>
                <p className="text-xs text-muted-foreground">{roleAt(c)}</p>
              </TableCell>
              <TableCell>
                <div className="flex justify-end gap-1">
                  {reachOf(c).map(({ channel, address }) => (
                    <button key={channel} type="button"
                            title={channel === "email" ? `Write to ${address}` : `Message on ${CHANNEL_LABELS[channel]}`}
                            aria-label={`${c.name ?? "Contact"} by ${CHANNEL_LABELS[channel]}`}
                            className={LINK} onClick={() => onOpen(c, channel)}>
                      <span className="relative">
                        <ChannelIcon channel={channel} />
                        {unread.get(c.id)?.[channel] ? (
                          <UnreadBadge count={unread.get(c.id)?.[channel] ?? 0} className="absolute -top-2 -right-2.5" />
                        ) : null}
                      </span>
                    </button>
                  ))}
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
              <TableCell className="text-right">
                <Button size="icon-sm" variant="ghost" title="Remove from contacts"
                        aria-label={`Remove ${c.name ?? c.email ?? "contact"}`} onClick={() => onRemove(c.id)}>
                  <Trash2 />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {people.length === 0 && <p className="text-sm text-muted-foreground">No contact matches “{query}”.</p>}
    </div>
  )
}
